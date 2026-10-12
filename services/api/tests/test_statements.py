from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.ai.llm import FakeLLM
from app.ai.offline import offline_llm
from app.models import Account, AIDecision, Instruction, Person, StatementLine
from app.seed.funds import seed_funds
from app.services.instructions import payment_reference
from app.services.reconciliation import code_of, edit_distance
from app.services.statements import (StatementError, extraction_from_document, ingest_statement, normalise,
                                     parse_csv, rule_reading, sample_lines, sample_statement)
from app.services.reconciliation import open_receipts

CSV = (b"Date,Description,Amount\n"
       b"10/12/2026,ACH CREDIT PRIYA RAMAN REF ATR-1A2B3C4D,\"1,500.00\"\n"
       b"2026-10-12,MONTHLY SERVICE FEE,(25.00)\n"
       b"10/12/2026,INTEREST PAID,3.42\n")


def entity(type_, text, money=None, day=None, properties=()):
    normalized = SimpleNamespace(money_value=money, date_value=day)
    return SimpleNamespace(type_=type_, mention_text=text, normalized_value=normalized, properties=list(properties))


def test_csv_statements_with_one_amount_column_or_two():
    one = parse_csv(CSV)
    assert [(x.value_date, x.amount) for x in one.lines] == [
        (date(2026, 10, 12), Decimal("1500.00")), (date(2026, 10, 12), Decimal("-25.00")),
        (date(2026, 10, 12), Decimal("3.42"))]
    two = parse_csv(b"Posting Date,Details,Deposits,Withdrawals\n2026-10-12,WIRE IN X,250.00,\n2026-10-12,FEE,,10\n")
    assert [x.amount for x in two.lines] == [Decimal("250.00"), Decimal("-10")]
    with pytest.raises(StatementError, match="needs a date column"):
        parse_csv(b"When,What\n1,2\n")


def test_document_ai_table_items_become_lines():
    money = SimpleNamespace(units=1500, nanos=0)
    document = SimpleNamespace(entities=[
        entity("bank_name", "Atrium Demo Bank, N.A."),
        entity("account_number", "000184527781"),
        entity("statement_start_date", "10/06/2026", day=SimpleNamespace(year=2026, month=10, day=6)),
        entity("table_item", "", properties=[
            entity("table_item/transaction_deposit", "1,500.00", money=money),
            entity("table_item/transaction_deposit_date", "10/12/2026"),
            entity("table_item/transaction_deposit_description", "ACH CREDIT PRIYA RAMAN\nREF ATR-1A2B3C4D")]),
        entity("table_item", "", properties=[
            entity("table_item/transaction_withdrawal", "25.00"),
            entity("table_item/transaction_withdrawal_date", "10/12/2026"),
            entity("table_item/transaction_withdrawal_description", "MONTHLY SERVICE FEE")])])
    result = extraction_from_document(document)
    assert result.source == "documentai" and result.bank_name == "Atrium Demo Bank, N.A."
    assert result.account_last4 == "7781" and result.period_start == date(2026, 10, 6)
    assert [(x.amount, x.description) for x in result.lines] == [
        (Decimal("1500"), "ACH CREDIT PRIYA RAMAN REF ATR-1A2B3C4D"), (Decimal("-25.00"), "MONTHLY SERVICE FEE")]


def test_rules_read_payer_reference_and_channel():
    ach = rule_reading(1, "ACH CREDIT PRIYA RAMAN REF ATR-1A2B3C4D")
    assert (ach.remitter, ach.reference, ach.channel) == ("Priya Raman", "ATR-1A2B3C4D", "ACH")
    wire = rule_reading(2, "WIRE IN LUCAS MOREAU ATR7F3K2Q11X")   # nine characters: not a reference
    assert wire.reference is None and wire.channel == "WIRE"
    assert rule_reading(3, "WIRE IN LUCAS MOREAU ATR7F3K2Q1D").reference == "ATR-7F3K2Q1D"
    fee = rule_reading(4, "MONTHLY SERVICE FEE")
    assert (fee.remitter, fee.channel) == (None, "FEE")


def test_gemini_reads_narrations_but_cannot_invent_a_reference(db):
    lines = parse_csv(CSV).lines
    llm = FakeLLM({"statement_normalise": {"lines": [
        {"line_no": 1, "remitter": "Priya Raman", "reference": "ATR-ZZZZZZZZ", "channel": "ACH"},
        {"line_no": 2, "remitter": None, "reference": None, "channel": "FEE"}]}})
    readings, reader = normalise(db, llm, "s1", lines)
    assert reader == "fake-llm" and readings[0].remitter == "Priya Raman"
    assert readings[0].reference == "ATR-1A2B3C4D"   # the invented reference is replaced by what the line says
    assert readings[2].channel == "INTEREST"          # a line Gemini skipped falls back to the rules
    assert db.scalars(select(AIDecision.purpose)).all() == ["statement_normalise"]


def test_ingesting_a_csv_keeps_deposits_and_refuses_duplicates(db, staff):
    statement = ingest_statement(db, data=CSV, filename="oct.csv", mime_type="text/csv", uploaded_by=staff["mei"],
                                 llm=offline_llm(), reader=None)
    lines = db.scalars(select(StatementLine).where(StatementLine.statement_id == statement.id)
                       .order_by(StatementLine.line_no)).all()
    assert [(x.state, x.reference) for x in lines] == [("unmatched", "ATR-1A2B3C4D"), ("ignored", None),
                                                        ("ignored", None)]
    assert statement.source == "csv" and statement.period_start == date(2026, 10, 12)
    with pytest.raises(StatementError, match="already been uploaded"):
        ingest_statement(db, data=CSV, filename="again.csv", mime_type="text/csv", uploaded_by=staff["mei"],
                         llm=offline_llm(), reader=None)
    with pytest.raises(StatementError, match="Upload the CSV version"):
        ingest_statement(db, data=b"%PDF-1.4", filename="oct.pdf", mime_type="application/pdf",
                         uploaded_by=staff["mei"], llm=offline_llm(), reader=None)
    with pytest.raises(StatementError, match="No transactions"):
        ingest_statement(db, data=b"Date,Description,Amount\n", filename="empty.csv", mime_type="text/csv",
                         uploaded_by=staff["mei"], llm=offline_llm(), reader=None)


def test_the_sample_statement_has_the_imperfections_of_a_real_one(db, account, staff):
    seed_funds(db)
    subs = []
    for minute, amount in enumerate(("1500", "2500", "3000", "1250", "5000")):
        row = Instruction(account_id=account.id, fund_code="ATR-BAL", type="subscribe", amount=Decimal(amount),
                          state="accepted", requested_at=datetime(2026, 10, 12, 13, minute, tzinfo=timezone.utc))
        db.add(row)
        db.flush()
        subs.append(row)
    lines = sample_lines(open_receipts(db), date(2026, 10, 12))
    words = [x.description for x in lines]
    assert words[0] == f"ACH CREDIT PRIYA RAMAN REF {payment_reference(subs[0].id)}"
    assert words[1] == f"WIRE IN PRIYA RAMAN ATR{code_of(payment_reference(subs[1].id))}"
    typo = code_of(words[2].rsplit(" ", 1)[1])
    assert edit_distance(typo, code_of(payment_reference(subs[2].id))) == 1
    assert words[3] == "ONLINE TRANSFER FROM PRIYA RAMAN"
    assert words[4].endswith("PART 1 OF 2") and lines[4].amount + lines[5].amount == Decimal("5000")
    assert {"INTEREST PAID", "MONTHLY SERVICE FEE"} <= set(words)
    pdf, name, mime = sample_statement(db, date(2026, 10, 12), "pdf")
    assert pdf.startswith(b"%PDF") and name.endswith(".pdf") and mime == "application/pdf"
    data, _, _ = sample_statement(db, date(2026, 10, 12), "csv")
    assert [x.amount for x in parse_csv(data).lines] == [x.amount for x in lines]
