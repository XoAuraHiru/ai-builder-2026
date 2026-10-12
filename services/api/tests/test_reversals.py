from datetime import date, datetime, timezone
from decimal import Decimal

import pyotp
import pytest
from sqlalchemy import select

from app.models import Instruction, InstructionStep, Posting
from app.seed.funds import seed_funds
from app.services.approvals import decide
from app.services.ledger import apply_posting, balance, holdings
from app.services.reversals import ReversalError, request_reversal

NOW = datetime(2026, 10, 12, 15, tzinfo=timezone.utc)


@pytest.fixture()
def allocated(db, account):
    seed_funds(db)
    instruction = Instruction(account_id=account.id, fund_code="ATR-BAL", type="subscribe", amount=Decimal("1000"),
                              state="allocated")
    db.add(instruction)
    db.flush()
    posting = apply_posting(db, account_id=account.id, instrument="ATR-BAL", instrument_type="fund",
                            posting_type="subscription", units=Decimal("10"), cash=Decimal("-1000"),
                            price=Decimal("100"), value_date=date(2026, 10, 9), reference=instruction.id)
    db.commit()
    return instruction, posting


def test_a_reversal_cancels_the_allocation_after_a_second_approval(db, account, staff, allocated):
    instruction, posting = allocated
    approval = request_reversal(db, posting.id, staff["mei"], "Allocated to the wrong account.")
    assert "10" in approval.summary and approval.payload == {"posting_id": posting.id}
    decide(db, approval, staff["sam"], approve=True, code=pyotp.TOTP(staff["sam"].totp_secret).at(NOW), now=NOW)
    reversal = db.scalar(select(Posting).where(Posting.reversal_of == posting.id))
    assert (reversal.posting_type, reversal.units, reversal.cash) == ("reversal", Decimal("-10"), Decimal("1000"))
    assert balance(db, account.id, "ATR-BAL") == Decimal("0") and holdings(db, account.id) == []
    assert instruction.state == "reversed"
    notes = db.scalars(select(InstructionStep.note).where(InstructionStep.instruction_id == instruction.id)).all()
    assert any("wrong account" in n for n in notes)
    with pytest.raises(ReversalError, match="already been reversed"):
        request_reversal(db, posting.id, staff["mei"], "Again.")


def test_only_an_intact_fund_allocation_can_be_reversed(db, account, staff, allocated):
    _, posting = allocated
    apply_posting(db, account_id=account.id, instrument="ATR-BAL", instrument_type="fund", posting_type="redemption",
                  units=Decimal("-3"), cash=Decimal("300"), price=Decimal("100"), value_date=date(2026, 10, 10),
                  reference="R1")
    with pytest.raises(ReversalError, match="since been redeemed"):
        request_reversal(db, posting.id, staff["mei"], "Wrong account.")
    cash = apply_posting(db, account_id=account.id, instrument="USD", instrument_type="cash", posting_type="deposit",
                         units=Decimal("500"), cash=Decimal("500"), price=Decimal("1"), value_date=date(2026, 10, 1),
                         reference="PAPER-CASH")
    with pytest.raises(ReversalError, match="Only a fund allocation"):
        request_reversal(db, cash.id, staff["mei"], "Wrong account.")
    with pytest.raises(ReversalError, match="not found"):
        request_reversal(db, "nope", staff["mei"], "Wrong account.")


def test_a_switch_is_not_reversed_one_leg_at_a_time(db, account, staff):
    seed_funds(db)
    switch = Instruction(account_id=account.id, fund_code="ATR-BAL", type="switch", units=Decimal("2"),
                         to_fund_code="ATR-INC", state="settled")
    db.add(switch)
    db.flush()
    apply_posting(db, account_id=account.id, instrument="ATR-BAL", instrument_type="fund", posting_type="subscription",
                  units=Decimal("20"), cash=Decimal("-2000"), price=Decimal("100"), value_date=date(2026, 10, 1),
                  reference="SEED")
    apply_posting(db, account_id=account.id, instrument="ATR-BAL", instrument_type="fund", posting_type="redemption",
                  units=Decimal("-2"), cash=Decimal("200"), price=Decimal("100"), value_date=date(2026, 10, 9),
                  reference=switch.id)
    inbound = apply_posting(db, account_id=account.id, instrument="ATR-INC", instrument_type="fund",
                            posting_type="subscription", units=Decimal("2"), cash=Decimal("-200"), price=Decimal("100"),
                            value_date=date(2026, 10, 9), reference=switch.id)
    db.commit()
    with pytest.raises(ReversalError, match="switch"):
        request_reversal(db, inbound.id, staff["mei"], "Wrong fund.")
