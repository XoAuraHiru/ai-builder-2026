from datetime import date, datetime, timezone
from decimal import Decimal

import pyotp
import pytest
from sqlalchemy import select

from app.models import (Account, BankStatement, Instruction, InstructionStep, Person, ReconMatch, StatementLine)
from app.seed.funds import seed_funds
from app.services.approvals import ApprovalError, decide
from app.services.instructions import payment_reference
from app.services.reconciliation import (ReconError, accept, code_of, edit_distance, fallback_proposals, name_similarity,
                                         open_receipts, propose_by_rules, reject, request_manual_match, score,
                                         unmatched_deposits)

NOW = datetime(2026, 10, 12, 15, tzinfo=timezone.utc)


@pytest.fixture()
def book(db, account, staff):
    seed_funds(db)
    lucas = Person(kind="investor", full_name="Lucas Moreau", email="lucas@example.test")
    db.add(lucas)
    db.flush()
    other = Account(person_id=lucas.id, number="ACC-0002", opened_on=date(2026, 1, 5))
    db.add(other)
    db.flush()

    def subscription(acc, amount, state="accepted"):
        row = Instruction(account_id=acc.id, fund_code="ATR-BAL", type="subscribe", amount=Decimal(amount), state=state,
                          requested_at=NOW)
        db.add(row)
        db.flush()
        return row

    statement = BankStatement(filename="s.csv", mime_type="text/csv", sha256="b" * 64, size_bytes=1, source="csv",
                              uploaded_by=staff["mei"].id, notes=[])
    db.add(statement)
    db.flush()
    lines = []

    def line(amount, description, remitter, reference=None):
        row = StatementLine(statement_id=statement.id, line_no=len(lines) + 1, value_date=date(2026, 10, 12),
                            amount=Decimal(amount), description=description, remitter=remitter, reference=reference)
        db.add(row)
        db.flush()
        lines.append(row)
        return row

    return {"priya": account, "lucas": other, "subscription": subscription, "line": line, "statement": statement}


def test_reference_codes_distances_and_names():
    assert code_of("ATR-1A2B3C4D") == "1A2B3C4D" and code_of("atr1a2b3c4d") == "1A2B3C4D" and code_of(None) is None
    assert code_of("INV 2231") is None
    assert edit_distance("1A2B3C4D", "1A2B3C4D") == 0 and edit_distance("1A2B3C4D", "1A2B3C0D") == 1
    assert name_similarity("PRIYA RAMAN", "Priya Raman") == 1.0 and name_similarity("Marcus Okonkwo", "Grace Li") == 0.0


def test_rules_take_exact_references_and_unique_amounts_only(db, book):
    exact = book["subscription"](book["priya"], "1500")
    unique = book["subscription"](book["lucas"], "2500")
    a = book["subscription"](book["priya"], "500")
    b = book["subscription"](book["lucas"], "500")
    typo = book["subscription"](book["lucas"], "3000")
    book["line"]("1500.00", f"ACH CREDIT PRIYA RAMAN REF {payment_reference(exact.id)}", "Priya Raman",
                 payment_reference(exact.id))
    book["line"]("2500.00", "ONLINE TRANSFER FROM LUCAS MOREAU", "Lucas Moreau")
    book["line"]("500.00", "ONLINE TRANSFER FROM P RAMAN", "P Raman")   # two subscriptions carry $500: ambiguous
    wrong = "ATR-" + code_of(payment_reference(typo.id))[:5] + ("0" if code_of(payment_reference(typo.id))[5] != "0" else "1") \
        + code_of(payment_reference(typo.id))[6:]
    book["line"]("3000.00", f"ACH CREDIT LUCAS MOREAU REF {wrong}", "Lucas Moreau", wrong)
    made = propose_by_rules(db)
    tiers = {m.instruction_ids[0]: (m.tier, m.confidence) for m in made}
    assert tiers == {exact.id: ("exact_reference", 0.99), unique.id: ("unique_amount", 0.85)}
    assert {a.id, b.id, typo.id}.isdisjoint(tiers)
    assert len(unmatched_deposits(db)) == 2 and propose_by_rules(db) == []   # nothing is proposed twice


def test_the_scorer_explains_a_mistyped_reference(db, book):
    sub = book["subscription"](book["lucas"], "3000")
    code = code_of(payment_reference(sub.id))
    wrong = f"ATR-{code[:5]}{'0' if code[5] != '0' else '1'}{code[6:]}"
    line = book["line"]("3000.00", f"ACH CREDIT LUCAS MOREAU REF {wrong}", "Lucas Moreau", wrong)
    receipt = next(r for r in open_receipts(db) if r.instruction_id == sub.id)
    found = score(line, receipt)
    assert found.score == 0.85 and "1 character away" in found.reasons[0]
    assert fallback_proposals([line], open_receipts(db))[0]["tier"] == "fuzzy"


def test_accepting_funds_or_settles_the_subscription(db, book, staff):
    waiting = book["subscription"](book["priya"], "1500")
    allocated = book["subscription"](book["lucas"], "2500", state="allocated")
    for sub, name in ((waiting, "PRIYA RAMAN"), (allocated, "LUCAS MOREAU")):
        ref = payment_reference(sub.id)
        book["line"](str(sub.amount), f"ACH CREDIT {name} REF {ref}", name.title(), ref)
    for match in propose_by_rules(db):
        accept(db, match, staff["mei"], NOW)
    assert allocated.state == "settled" and waiting.state == "accepted"
    steps = db.scalars(select(InstructionStep.state).where(InstructionStep.instruction_id == waiting.id)).all()
    assert steps == ["funded"] and open_receipts(db) == []
    assert {line.state for line in db.scalars(select(StatementLine)).all()} == {"matched"}


def test_rejecting_frees_the_lines(db, book, staff):
    sub = book["subscription"](book["priya"], "1500")
    ref = payment_reference(sub.id)
    book["line"]("1500.00", f"ACH CREDIT PRIYA RAMAN REF {ref}", "Priya Raman", ref)
    match = propose_by_rules(db)[0]
    reject(db, match, staff["mei"], NOW, "Paid twice; returning one.")
    assert match.state == "rejected" and [line.state for line in unmatched_deposits(db)] == ["unmatched"]
    with pytest.raises(ReconError, match="already been decided"):
        accept(db, match, staff["mei"], NOW)


def test_a_manual_match_needs_a_second_person(db, book, staff):
    sub = book["subscription"](book["priya"], "1500")
    first = book["line"]("1000.00", "CHECK DEPOSIT 1043", None)
    second = book["line"]("500.00", "CHECK DEPOSIT 1044", None)
    approval = request_manual_match(db, [first.id, second.id], [sub.id], staff["mei"],
                                    "Two checks from the client, confirmed by phone.")
    match = db.scalar(select(ReconMatch))
    assert match.state == "awaiting_approval" and match.tier == "manual" and "agree" in match.evidence[0]
    with pytest.raises(ReconError, match="second person"):
        accept(db, match, staff["mei"], NOW)
    with pytest.raises(ApprovalError, match="different person"):
        decide(db, approval, staff["mei"], approve=True, code=pyotp.TOTP(staff["mei"].totp_secret).at(NOW), now=NOW)
    decide(db, approval, staff["sam"], approve=True, code=pyotp.TOTP(staff["sam"].totp_secret).at(NOW), now=NOW)
    assert match.state == "accepted" and match.decided_by == staff["sam"].id
    assert first.state == "matched" and approval.result["match_id"] == match.id


def test_a_rejected_manual_match_frees_its_lines(db, book, staff):
    sub = book["subscription"](book["priya"], "1500")
    line = book["line"]("1500.00", "CHECK DEPOSIT 1045", None)
    approval = request_manual_match(db, [line.id], [sub.id], staff["mei"], "Check from the client.")
    decide(db, approval, staff["sam"], approve=False, code=pyotp.TOTP(staff["sam"].totp_secret).at(NOW), now=NOW)
    assert db.scalar(select(ReconMatch.state)) == "rejected" and line.state == "unmatched"
    with pytest.raises(ReconError, match="still waiting"):
        request_manual_match(db, [line.id], ["nope"], staff["mei"], "Check.")
