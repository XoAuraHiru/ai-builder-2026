from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from app.seed.funds import seed_funds
from app.services.ledger import apply_posting
from app.services.portfolio import PriceUnavailable, valuation
from app.services.pricing import publish_prices


@pytest.fixture()
def priced_funds(db):
    seed_funds(db)
    idx = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])
    publish_prices(db, "ATR-BAL", pd.Series([100.0, 102.0, 104.0], index=idx), Decimal("1000000"))
    publish_prices(db, "ATR-TEC", pd.Series([200.0, 190.0, 210.0], index=idx), Decimal("500000"))
    db.commit()


def buy(db, account, fund, units, price, day):
    apply_posting(db, account_id=account.id, instrument=fund, instrument_type="fund", posting_type="subscription",
                  units=Decimal(units), cash=-Decimal(units) * Decimal(price), price=Decimal(price), value_date=day,
                  reference=f"SUB-{fund}")
    db.commit()


def test_valuation_totals_and_lookthrough(db, account, priced_funds):
    buy(db, account, "ATR-BAL", "100", "100", date(2026, 1, 2))
    buy(db, account, "ATR-TEC", "10", "200", date(2026, 1, 2))
    view = valuation(db, account.id, date(2026, 1, 6))
    assert view.total_value == Decimal("12500.00")  # 100*104 + 10*210
    assert view.total_cost == Decimal("12000.00")
    assert view.pnl == Decimal("500.00")
    assert view.by_fund["ATR-BAL"] == Decimal("10400.00")
    assert view.by_asset_class["bond"] == Decimal("4160.00")  # 40% of ATR-BAL
    assert view.by_asset_class["equity"] == Decimal("8340.00")  # 6240 + 2100
    assert view.by_region["US"] == Decimal("12500.00")
    tec = next(h for h in view.holdings if h.instrument == "ATR-TEC")
    assert tec.pnl_pct == Decimal("5.00")


def test_valuation_uses_last_price_on_or_before_as_of(db, account, priced_funds):
    buy(db, account, "ATR-BAL", "10", "100", date(2026, 1, 2))
    view = valuation(db, account.id, date(2026, 1, 4))  # Sunday
    assert view.holdings[0].price_as_of == date(2026, 1, 2)
    assert view.total_value == Decimal("1000.00")


def test_valuation_raises_when_no_price_exists_yet(db, account, priced_funds):
    buy(db, account, "ATR-BAL", "10", "100", date(2026, 1, 2))
    with pytest.raises(PriceUnavailable):
        valuation(db, account.id, date(2026, 1, 1))


def test_portfolio_for_empty_account_is_zero(client, account, priced_funds):
    r = client.get(f"/accounts/{account.id}/portfolio?as_of=2026-01-06")
    assert r.status_code == 200
    body = r.json()
    assert body["total_value"] == "0.00" and body["holdings"] == [] and body["by_fund"] == {}


def test_portfolio_endpoint_returns_view(client, db, account, priced_funds):
    buy(db, account, "ATR-BAL", "100", "100", date(2026, 1, 2))
    r = client.get(f"/accounts/{account.id}/portfolio?as_of=2026-01-06")
    assert r.status_code == 200
    body = r.json()
    assert body["total_value"] == "10400.00"
    assert body["holdings"][0]["name"] == "Atrium Balanced"
    assert body["holdings"][0]["price_as_of"] == "2026-01-06"


def test_unknown_account_returns_404(client, account, priced_funds):
    r = client.get("/accounts/nope/portfolio")
    assert r.status_code == 404 and "account" in r.json()["detail"].lower()


def test_funds_endpoints(client, priced_funds):
    r = client.get("/funds")
    assert r.status_code == 200 and len(r.json()) == 7
    one = client.get("/funds/ATR-BAL").json()
    assert one["name"] == "Atrium Balanced" and len(one["constituents"]) == 2
    prices = client.get("/funds/ATR-BAL/prices?start=2026-01-05&end=2026-01-06").json()
    assert [p["as_of"] for p in prices] == ["2026-01-05", "2026-01-06"]


def test_unknown_fund_returns_404(client, priced_funds):
    assert client.get("/funds/NOPE").status_code == 404
    assert client.get("/funds/NOPE/prices").status_code == 404
