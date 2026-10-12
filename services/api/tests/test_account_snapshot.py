from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd
import pytest

from app.markets.quotes import CommittedQuotes
from app.models import LeadConversion, Person, TradeOrder
from app.services.account_snapshot import Sale, account_snapshot, trading_days_back
from app.services.devices import see_device

NOW = datetime(2026, 10, 9, 15, tzinfo=timezone.utc)  # Friday, 11:00 in New York
DAILY = pd.DataFrame({"AAPL": [190.0, 200.0, 210.0], "KO": [60.0, 61.0, 58.0]},
                     index=pd.to_datetime(["2026-10-02", "2026-10-08", "2026-10-09"]))


def order(account, side, symbol, qty, value, state):
    return TradeOrder(account_id=account.id, symbol=symbol, side=side, order_type="limit", quantity=qty,
                      limit_price=Decimal("100"), state=state, verdict="proceed", guardian={}, estimated_value=Decimal(value),
                      broker="atrium-paper", trust_score=100, trust_band="clear", timeline=[])


@pytest.fixture()
def trader(db, account, paper):
    paper.deposit(account, "10000")
    paper.trade(account, "buy", "AAPL", 10, "190", day=date(2026, 10, 2))
    db.add_all([order(account, "buy", "KO", 10, "600.00", "held"), order(account, "sell", "AAPL", 4, "800.00", "open"),
                order(account, "buy", "KO", 99, "9999.00", "filled")])
    db.commit()
    return account


def snap(db, account, **kw):
    return account_snapshot(db, account, device_hash=kw.pop("device_hash", None), now=NOW,
                            quotes=CommittedQuotes(DAILY), **kw)


def test_cash_and_shares_promised_to_waiting_orders_are_set_aside(db, trader):
    s = snap(db, trader)
    assert s.cash == Decimal("8100.00") and s.reserved_cash == Decimal("600.00") and s.cash_free == Decimal("7500.00")
    assert s.units == {"AAPL": Decimal("10.000000")} and s.units_free("AAPL") == Decimal("6.000000")
    assert sum(lot.units for lot in s.lots["AAPL"]) == Decimal("6.000000")
    assert s.traded_value == Decimal("2100.00") and s.weights == {"AAPL": 2100.0, "USD": 8100.0}
    held = next(o for o in trader_orders(db, trader) if o.state == "held")
    assert snap(db, trader, exclude_order=held.id).reserved_cash == Decimal("0")


def trader_orders(db, account):
    from sqlalchemy import select
    return db.scalars(select(TradeOrder).where(TradeOrder.account_id == account.id)).all()


def test_recent_sales_purchases_and_day_trades(db, account, paper):
    paper.deposit(account, "10000")
    paper.trade(account, "buy", "KO", 5, "60", day=date(2026, 10, 9))
    paper.trade(account, "sell", "KO", 5, "58", day=date(2026, 10, 9))
    paper.trade(account, "buy", "AAPL", 2, "200", day=date(2026, 10, 8))
    db.commit()
    s = snap(db, account)
    assert s.sales == [Sale("KO", date(2026, 10, 9), Decimal("-10.00"))]
    assert sorted(s.buys) == [("AAPL", date(2026, 10, 8)), ("KO", date(2026, 10, 9))]
    assert s.day_trades == 1 and s.traded_today == {"KO": {"buy", "sell"}}


def test_trust_inputs_read_the_lead_device_and_activity(db, account, make_lead):
    lead = make_lead()
    db.add(LeadConversion(lead_id=lead.id, person_id=account.person_id, account_id=account.id,
                          converted_by="daniel@atrium.demo", trust_score=72, trust_band="review"))
    see_device(db, account.id, "known", "Chrome on Windows", NOW - timedelta(days=30))
    db.commit()
    t = snap(db, account, device_hash="known").trust
    assert (t.baseline, t.device_sent, t.device_first_seen) == (72, True, NOW - timedelta(days=30))
    assert t.last_activity is None and t.recent_orders == 0
    unknown = snap(db, account).trust
    assert unknown.device_sent is False and unknown.baseline_source == "the lead's trust score at conversion"


def test_profile_band_comes_from_the_person(db, account):
    db.get(Person, account.person_id).risk_band = 2
    db.commit()
    assert snap(db, account).profile_band == 2


def test_five_trading_days_back_skips_weekends():
    assert trading_days_back(date(2026, 10, 9), 5) == date(2026, 10, 5)
    assert trading_days_back(date(2026, 10, 12), 5) == date(2026, 10, 6)
