from datetime import date, datetime, timezone
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import select

from app.models import STEP_STATES, Fund, Instruction, InstructionStep, Price, ReconMatch, RecurringPlan
from app.realtime.inbox import set_courier
from app.seed.funds import seed_funds
from app.services.allocation import allocate, create_due_recurring, dealing_day, settle
from app.services.ledger import apply_posting, balance
from app.services.pricing import publish_prices

AS_OF = date(2026, 10, 9)                                  # a Friday
MORNING = datetime(2026, 10, 9, 14, tzinfo=timezone.utc)   # 10:00 in New York
EVENING = datetime(2026, 10, 9, 21, tzinfo=timezone.utc)   # 17:00 in New York, after the cut-off


def utc(text):
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


@pytest.fixture()
def priced(db):
    seed_funds(db)
    for code in db.scalars(select(Fund.code)).all():
        publish_prices(db, code, pd.Series([100.0], index=pd.to_datetime([AS_OF])), Decimal("1000"))
    db.commit()


def instruction(db, account, kind, fund="ATR-BAL", amount=None, units=None, to=None, at=MORNING):
    row = Instruction(account_id=account.id, fund_code=fund, type=kind, state="accepted", requested_at=at,
                      amount=Decimal(amount) if amount else None, units=Decimal(units) if units else None,
                      to_fund_code=to)
    db.add(row)
    db.flush()
    return row


def steps(db, row):
    states = db.scalars(select(InstructionStep.state).where(InstructionStep.instruction_id == row.id)).all()
    return sorted(states, key=STEP_STATES.index)


def test_the_dealing_day_follows_the_new_york_cut_off():
    assert dealing_day(utc("2026-10-12T14:00:00")) == date(2026, 10, 12)   # Monday 10:00
    assert dealing_day(utc("2026-10-12T21:00:00")) == date(2026, 10, 13)   # Monday 17:00
    assert dealing_day(utc("2026-10-09T21:00:00")) == date(2026, 10, 12)   # Friday evening: Monday
    assert dealing_day(utc("2026-10-10T15:00:00")) == date(2026, 10, 12)   # Saturday: Monday


def test_subscriptions_redemptions_and_switches_are_dealt_at_the_price(db, account, priced):
    apply_posting(db, account_id=account.id, instrument="ATR-BAL", instrument_type="fund", posting_type="subscription",
                  units=Decimal("20"), cash=Decimal("-2000"), price=Decimal("100"), value_date=date(2026, 10, 1),
                  reference="SEED")
    sub = instruction(db, account, "subscribe", amount="1000")
    red = instruction(db, account, "redeem", units="5")
    swi = instruction(db, account, "switch", units="2", to="ATR-INC")
    late = instruction(db, account, "subscribe", amount="500", at=EVENING)
    report = allocate(db, AS_OF, EVENING)
    assert report.blocked == [] and len(report.allocated) == 3
    assert (sub.state, red.state, swi.state, late.state) == ("allocated", "settled", "settled", "accepted")
    assert balance(db, account.id, "ATR-BAL") == Decimal("23")   # 20 + 10 - 5 - 2
    assert balance(db, account.id, "ATR-INC") == Decimal("2")
    assert sub.dealing_date == AS_OF and steps(db, sub) == ["priced", "allocated"]
    assert steps(db, red) == ["priced", "allocated", "settled"]
    assert allocate(db, AS_OF, EVENING).allocated == []   # nothing is dealt twice


def test_a_funded_subscription_settles_on_allocation(db, account, priced):
    sub = instruction(db, account, "subscribe", amount="1000")
    db.add(ReconMatch(line_ids=["l1"], instruction_ids=[sub.id], tier="exact_reference", confidence=0.99,
                      evidence=[], proposed_by="rules", state="accepted"))
    allocate(db, AS_OF, EVENING)
    assert sub.state == "settled" and sub.settled_at == EVENING


def test_a_redemption_the_holding_cannot_cover_is_rejected(db, account, priced):
    red = instruction(db, account, "redeem", units="5")
    report = allocate(db, AS_OF, EVENING)
    assert red.state == "rejected" and report.rejected[0]["instruction_id"] == red.id
    assert "holding" in report.rejected[0]["reason"]


def test_nothing_is_dealt_while_a_fund_is_unpriced(db, account, priced):
    db.delete(db.scalar(select(Price).where(Price.fund_code == "ATR-TEC")))
    sub = instruction(db, account, "subscribe", amount="1000")
    report = allocate(db, AS_OF, EVENING)
    assert report.blocked == ["ATR-TEC"] and report.allocated == [] and sub.state == "accepted"


def test_dealing_tells_the_holder_once_per_instruction_with_the_units_and_the_price(db, account, priced, inbox):
    apply_posting(db, account_id=account.id, instrument="ATR-BAL", instrument_type="fund", posting_type="subscription",
                  units=Decimal("20"), cash=Decimal("-2000"), price=Decimal("100"), value_date=date(2026, 10, 1),
                  reference="SEED")
    sub = instruction(db, account, "subscribe", amount="1000")
    red = instruction(db, account, "redeem", units="5")
    swi = instruction(db, account, "switch", units="2", to="ATR-INC")
    allocate(db, AS_OF, EVENING)
    assert inbox.sent == []  # nothing leaves before the commit
    db.commit()
    told = {t.id: t for t in inbox.to(account.person_id)}
    assert set(told) == {f"fund_order_dealt-{i.id}" for i in (sub, red, swi)}
    dealt = told[f"fund_order_dealt-{sub.id}"]
    assert (dealt.kind, dealt.stage, dealt.severity, dealt.href, dealt.actor) == (
        "fund_order_dealt", "invest", "info", "/investor/orders", "Day-end")
    assert dealt.title == "Dealt: 10.0000 units of Atrium Balanced at $100.00"
    assert dealt.body == "Units are in your account. Your order history has every step."
    assert told[f"fund_order_dealt-{red.id}"].title == "Dealt: $500.00 out of Atrium Balanced at $100.00"
    assert told[f"fund_order_dealt-{red.id}"].body == "Settled: $500.00 paid to the bank account ending ????."
    assert told[f"fund_order_dealt-{swi.id}"].title == ("Dealt: 2.0000 units of Atrium Core Income at $100.00, from "
                                                        "2.0000 units of Atrium Balanced")
    assert told[f"fund_order_dealt-{swi.id}"].body == "Settled: the switch is complete."
    allocate(db, AS_OF, EVENING)  # nothing is dealt twice, so no one is told twice
    db.commit()
    assert len(inbox.sent) == 3
    settle(db, sub, EVENING, "Settled: the payment was matched on the bank statement (exact reference).")
    db.commit()  # the payment arriving later rewrites the one notice with the settle note
    again = inbox.sent[-1].item
    assert again.id == dealt.id and again.title == dealt.title
    assert again.body == "Settled: the payment was matched on the bank statement (exact reference)."


def test_a_rejected_instruction_and_an_inbox_that_is_off_tell_no_one(db, account, priced, inbox):
    instruction(db, account, "redeem", units="5")  # nothing is held, so the day-end job rejects it
    allocate(db, AS_OF, EVENING)
    db.commit()
    assert inbox.sent == []
    set_courier(None)
    instruction(db, account, "subscribe", amount="1000")
    allocate(db, AS_OF, EVENING)
    db.commit()
    assert inbox.sent == []


def test_a_monthly_plan_contribution_tells_the_holder_it_is_accepted(db, account, priced, inbox):
    db.add(RecurringPlan(account_id=account.id, fund_code="ATR-GRW", amount=Decimal("250"), day_of_month=5,
                         status="active", created_at=utc("2026-09-20T12:00:00")))
    db.flush()
    [made] = create_due_recurring(db, AS_OF, EVENING)
    db.commit()
    [told] = inbox.to(account.person_id)
    assert (told.id, told.title) == (f"fund_order_accepted-{made.id}",
                                     "Accepted: $250.00 into Atrium Growth, your monthly plan")
    assert told.body == ("It will be dealt at the next published price. Monthly plans are exempt from the fund's "
                         "lump-sum minimum.")


def test_monthly_plans_become_subscriptions_once_a_month(db, account, priced):
    old = RecurringPlan(account_id=account.id, fund_code="ATR-BAL", amount=Decimal("50"), day_of_month=5,
                        status="active", created_at=utc("2026-09-20T12:00:00"))
    new = RecurringPlan(account_id=account.id, fund_code="ATR-GRW", amount=Decimal("75"), day_of_month=5,
                        status="active", created_at=utc("2026-10-08T12:00:00"))
    db.add_all([old, new])
    db.flush()
    made = create_due_recurring(db, AS_OF, EVENING)
    assert [(i.fund_code, i.amount, i.state) for i in made] == [("ATR-BAL", Decimal("50"), "accepted")]
    assert create_due_recurring(db, AS_OF, EVENING) == []
