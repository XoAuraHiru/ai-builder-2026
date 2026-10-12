from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import AmlAlert, Approval, BankStatement, Instruction, OpsRun, ReconMatch, StatementLine
from app.seed.funds import seed_funds
from app.seed.migrate import POSTGRES_MIGRATIONS
from app.services.instructions import payment_reference


def test_operations_tables_keep_their_rows(db, account, staff):
    approval = Approval(action="publish_prices", payload={"as_of": "2026-10-09"}, payload_hash="x" * 64,
                        summary="Publish prices for October 9", reason="Checked against the market.", evidence=[],
                        requested_by=staff["mei"].id)
    statement = BankStatement(filename="oct.csv", mime_type="text/csv", sha256="a" * 64, size_bytes=10, source="csv",
                              uploaded_by=staff["mei"].id, notes=[])
    db.add_all([approval, statement])
    db.flush()
    line = StatementLine(statement_id=statement.id, line_no=1, value_date=date(2026, 10, 9),
                         amount=Decimal("1500.00"), description="ACH CREDIT PRIYA RAMAN REF ATR-1A2B3C4D")
    db.add(line)
    db.flush()
    db.add_all([
        ReconMatch(line_ids=[line.id], instruction_ids=["i1"], tier="exact_reference", confidence=0.99,
                   evidence=["The reference matches."], proposed_by="rules"),
        AmlAlert(scenario="structuring", title="Possible structuring", severity="high", score=0.9,
                 person_id=account.person_id, account_id=account.id, summary="Three deposits just under $10,000.",
                 evidence=[], fingerprint="f" * 64),
        OpsRun(kind="day_end", as_of=date(2026, 10, 9), triggered_by="test", status="ok", steps=[])])
    db.commit()
    assert db.scalar(select(StatementLine.state)) == "unmatched"
    assert db.scalar(select(ReconMatch.state)) == "proposed" and db.scalar(select(AmlAlert.state)) == "open"
    assert db.scalar(select(Approval.state)) == "pending"


def test_new_columns_on_existing_tables_are_migrated():
    migrated = {(table, column) for table, column, _ in POSTGRES_MIGRATIONS}
    assert {("person", "totp_secret"), ("account", "bank_index")} <= migrated


def test_payment_reference_is_short_and_easy_to_read():
    assert payment_reference("1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d") == "ATR-1A2B3C4D"


def test_subscriptions_show_their_payment_reference(client, db, account):
    seed_funds(db)
    instruction = Instruction(account_id=account.id, fund_code="ATR-BAL", type="subscribe", amount=Decimal("1000"),
                              state="accepted")
    db.add(instruction)
    db.commit()
    body = client.get(f"/accounts/{account.id}/instructions", headers={"X-Dev-User": "priya@example.test"}).json()
    assert body[0]["payment_reference"] == payment_reference(instruction.id)
