from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from app.models import Fund, FundConstituent, Price
from app.seed.funds import seed_funds
from app.services.unit_history import unit_history


def fund():
    return Fund(code="F", name="Fund F", category="balanced", risk_band=3, fee_bps=0, min_investment=Decimal("0"),
                objective="", who_for="", inception_on=date(2010, 4, 1),
                constituents=[FundConstituent(ticker="AAA", weight=Decimal("1"), asset_class="equity", region="US",
                                              sector="broad")])


def returns(values):
    return pd.DataFrame({"AAA": values}, index=pd.date_range("2010-01-01", periods=len(values), freq="MS"))


def test_backtest_joins_the_first_published_price():
    published = [(date(2010, 4, 1), Decimal("50")), (date(2010, 4, 2), Decimal("51"))]
    points = unit_history(fund(), published, returns([0.10, -0.20, 0.25, 0.05, 0.05]))
    backtest = [p for p in points if p["backtest"]]
    # Jan, Feb and Mar month ends are before launch, plus the level the series starts from (end of December)
    assert [p["date"] for p in backtest] == [date(2009, 12, 31), date(2010, 1, 31), date(2010, 2, 28),
                                             date(2010, 3, 31)]
    assert backtest[-1]["price"] == 50.0                      # joins the first published price
    assert backtest[-2]["price"] == pytest.approx(50 / 1.25)  # March's +25% leads into it
    assert backtest[0]["price"] == pytest.approx(50 / 1.25 / 0.8 / 1.1)
    assert [p["price"] for p in points if not p["backtest"]] == [50.0, 51.0]


def test_without_published_prices_the_backtest_starts_at_100():
    points = unit_history(fund(), [], returns([0.10, -0.20]))
    assert all(p["backtest"] for p in points)
    assert [p["price"] for p in points] == [100.0, 110.0, 88.0]


def test_unit_history_is_public_and_flags_points_before_launch(client, db):
    seed_funds(db)
    db.add_all([Price(fund_code="ATR-BAL", as_of=date(2024, 10, 1), nav=Decimal("100"), status="published"),
                Price(fund_code="ATR-BAL", as_of=date(2024, 10, 2), nav=Decimal("100.5"), status="published"),
                Price(fund_code="ATR-BAL", as_of=date(2024, 10, 3), nav=Decimal("101"), status="draft")])
    db.commit()
    r = client.get("/funds/ATR-BAL/unit-history")
    assert r.status_code == 200, r.text
    points = r.json()["points"]
    assert points[0]["date"].startswith("2007") and points[0]["backtest"]
    published = [p for p in points if not p["backtest"]]
    assert [p["price"] for p in published] == [100.0, 100.5]  # drafts are never shown
    last_backtest = [p for p in points if p["backtest"]][-1]
    assert last_backtest["date"] == "2024-09-30" and last_backtest["price"] == 100.0


def test_unknown_fund_is_404(client, db):
    assert client.get("/funds/NOPE/unit-history").status_code == 404
