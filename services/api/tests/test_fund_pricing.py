from datetime import date, datetime, timezone
from decimal import Decimal

import pandas as pd
import pyotp
import pytest
from sqlalchemy import select

from app.events import current_bus
from app.models import Fund, Instruction, Price
from app.seed.funds import all_tickers, seed_funds
from app.services.approvals import decide
from app.services.fund_pricing import PricingError, draft_prices, last_closed_session, price_checks, request_publish
from app.services.pricing import pricing_guard, publish_prices

PREV, AS_OF = date(2026, 10, 8), date(2026, 10, 9)
NOW = datetime(2026, 10, 9, 21, tzinfo=timezone.utc)


def utc(text):
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


@pytest.fixture()
def funds(db):
    seed_funds(db)
    for code in db.scalars(select(Fund.code)).all():
        publish_prices(db, code, pd.Series([100.0], index=pd.to_datetime([PREV])), Decimal("1000"))
    db.commit()


def closes(xlk_close=120.0, drop=None):
    frame = pd.DataFrame({t: [100.0, 101.0] for t in all_tickers()}, index=pd.to_datetime([PREV, AS_OF]))
    frame.loc[pd.Timestamp(AS_OF), "XLK"] = xlk_close
    if drop:
        frame.loc[pd.Timestamp(AS_OF), drop] = float("nan")
    return frame


def code_for(person):
    return pyotp.TOTP(person.totp_secret).at(NOW)


def test_the_last_closed_session_is_new_york_time():
    assert last_closed_session(utc("2026-10-12T20:30:00")) == date(2026, 10, 12)   # Monday 16:30
    assert last_closed_session(utc("2026-10-12T15:00:00")) == date(2026, 10, 9)    # Monday 11:00
    assert last_closed_session(utc("2026-10-10T15:00:00")) == date(2026, 10, 9)    # Saturday


def test_drafts_move_each_nav_by_its_basket_and_are_made_once(db, funds):
    made, skipped = draft_prices(db, AS_OF, closes())
    navs = {p.fund_code: p.nav for p in made}
    assert len(made) == 7 and skipped == [] and {p.status for p in made} == {"draft"}
    assert navs["ATR-BAL"] == Decimal("101.000000")
    assert navs["ATR-TEC"] == Decimal("112.400000")   # XLK +20% at 60%, VGT +1% at 40%
    assert draft_prices(db, AS_OF, closes()) == ([], [])
    assert len(pricing_guard(db, AS_OF)) == 7         # drafts are not published prices


def test_a_fund_without_closes_is_skipped_and_named(db, funds):
    made, skipped = draft_prices(db, AS_OF, closes(drop="VGT"))
    assert "ATR-TEC" in skipped and "ATR-TEC" not in {p.fund_code for p in made}


def test_checks_flag_a_large_move(db, funds):
    draft_prices(db, AS_OF, closes())
    views = {v.fund_code: v for v in price_checks(db, AS_OF)}
    tec = next(c for c in views["ATR-TEC"].checks if c.code == "MOVE")
    assert not tec.ok and "12.4%" in tec.detail
    assert all(c.ok for c in views["ATR-BAL"].checks) and views["ATR-BAL"].move_pct == 1.0


def test_publication_needs_a_second_person_and_then_allocates(db, funds, account, staff):
    sub = Instruction(account_id=account.id, fund_code="ATR-BAL", type="subscribe", amount=Decimal("1010"),
                      state="accepted", requested_at=utc("2026-10-09T14:00:00"))
    db.add(sub)
    draft_prices(db, AS_OF, closes())
    approval = request_publish(db, AS_OF, staff["mei"], "Checked: Technology moved with XLK.")
    assert approval.payload["prices"]["ATR-BAL"] == "101.000000" and len(approval.evidence) == 7
    assert {p.status for p in db.scalars(select(Price).where(Price.as_of == AS_OF)).all()} == {"checked"}
    decide(db, approval, staff["sam"], approve=True, code=code_for(staff["sam"]), now=NOW)
    assert pricing_guard(db, AS_OF) == [] and approval.result["published"] == 7
    assert sub.state == "allocated" and approval.result["allocation"]["allocated"][0]["instruction_id"] == sub.id
    assert [e.type for e in current_bus().history].count("PricePublished") >= 7


def test_publication_needs_drafts(db, funds, staff):
    with pytest.raises(PricingError, match="No draft prices"):
        request_publish(db, AS_OF, staff["mei"], "Checked.")
