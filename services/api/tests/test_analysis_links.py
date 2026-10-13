from decimal import Decimal

import pandas as pd
import pytest

from app.markets.broker import PaperBroker, broker_dep
from app.markets.quotes import CommittedQuotes, quote_book
from app.models import Analysis, Instruction, Person, RecurringPlan, TradeOrder
from app.seed.funds import seed_funds
from app.services.pricing import publish_prices

HDR = {"X-Dev-User": "priya@example.test", "X-Device-Id": "browser-1"}
DAILY = pd.DataFrame({"KO": [60.0, 61.0]}, index=pd.to_datetime(["2026-10-08", "2026-10-09"]))


@pytest.fixture()
def holder(client, db, account, paper):
    seed_funds(db)
    idx = pd.to_datetime(["2026-01-02", "2026-01-05"])
    publish_prices(db, "ATR-BAL", pd.Series([100.0, 110.0], index=idx), Decimal("1000000"))
    paper.deposit(account, "10000")
    db.get(Person, account.person_id).risk_band = 3
    db.commit()
    client.app.dependency_overrides[quote_book] = lambda: CommittedQuotes(DAILY)
    client.app.dependency_overrides[broker_dep] = PaperBroker
    return account


def analysis(db, *, kind="unit_trust", code="ATR-BAL", monthly="200", person_id=None):
    row = Analysis(kind=kind, code=code, name=code, initial_usd=Decimal("1000"), monthly_usd=Decimal(monthly),
                   years=10, summary={}, person_id=person_id, device_id="device-1")
    db.add(row)
    db.commit()
    return row.id


def subscribe(client, account, **extra):
    return client.post(f"/accounts/{account.id}/instructions", headers=HDR,
                       json={"type": "subscribe", "fund_code": "ATR-BAL", "amount_usd": "1000", **extra})


def monthly(client, account, **extra):
    return client.post(f"/accounts/{account.id}/recurring", headers=HDR,
                       json={"fund_code": "ATR-BAL", "amount_usd": "200", "day_of_month": 5, **extra})


def buy(client, account, symbol="KO", side="buy", **extra):
    return client.post(f"/accounts/{account.id}/orders", headers=HDR,
                       json={"symbol": symbol, "side": side, "quantity": 2, "acknowledge_warnings": True, **extra})


def test_fund_order_and_monthly_plan_record_an_anonymous_analysis(client, db, holder):
    a = analysis(db)
    r = subscribe(client, holder, analysis_id=a)
    assert r.status_code == 201, r.text
    assert db.get(Instruction, r.json()["id"]).analysis_id == a
    r = monthly(client, holder, analysis_id=a)
    assert r.status_code == 201, r.text
    assert db.get(RecurringPlan, r.json()["id"]).analysis_id == a


def test_share_order_records_the_investors_own_analysis(client, db, holder):
    a = analysis(db, kind="share", code="KO", monthly="0", person_id=holder.person_id)
    r = buy(client, holder, analysis_id=a)
    assert r.status_code == 201, r.text
    assert db.get(TradeOrder, r.json()["id"]).analysis_id == a


def test_orders_without_an_analysis_are_unchanged(client, db, holder):
    assert subscribe(client, holder).status_code == 201
    assert buy(client, holder).status_code == 201


@pytest.mark.parametrize("make, send, message", [
    (dict(kind="share", code="KO"), subscribe, "was for KO"),
    (dict(code="ATR-GRW"), subscribe, "was for ATR-GRW"),
    (dict(code="ATR-BAL"), buy, "was for ATR-BAL"),
    (dict(kind="share", code="AAPL", monthly="0"), buy, "was for AAPL"),
    (dict(monthly="0"), monthly, "no monthly amount"),
])
def test_an_analysis_for_something_else_is_refused(client, db, holder, make, send, message):
    r = send(client, holder, analysis_id=analysis(db, **make))
    assert r.status_code == 422 and message in r.json()["detail"]


def test_someone_elses_analysis_is_refused_and_nothing_is_created(client, db, holder, people):
    a = analysis(db, person_id=people["advisor"].id)
    r = subscribe(client, holder, analysis_id=a)
    assert r.status_code == 422 and "someone else" in r.json()["detail"]
    assert db.query(Instruction).count() == 0


def test_unknown_analysis_is_refused(client, db, holder):
    r = buy(client, holder, analysis_id="nope")
    assert r.status_code == 422 and "not found" in r.json()["detail"]


def test_an_analysis_cannot_lead_to_a_sale_or_redemption(client, db, holder):
    r = buy(client, holder, side="sell", analysis_id=analysis(db, kind="share", code="KO", monthly="0"))
    assert r.status_code == 422 and "purchase" in r.json()["detail"]
    r = client.post(f"/accounts/{holder.id}/instructions", headers=HDR,
                    json={"type": "redeem", "fund_code": "ATR-BAL", "amount_usd": "100", "analysis_id": analysis(db)})
    assert r.status_code == 422 and "redemption" in r.json()["detail"]
