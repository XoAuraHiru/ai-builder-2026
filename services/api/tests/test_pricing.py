from datetime import date
from decimal import Decimal

import pandas as pd
from sqlalchemy import select

from app.models import Fund, Price
from app.seed.funds import seed_funds
from app.services.pricing import build_nav_series, latest_price, pricing_guard, publish_prices


def test_seed_funds_creates_seven_funds_with_weights_summing_to_one(db):
    funds = seed_funds(db)
    db.commit()
    assert len(funds) == 7
    assert {f.code for f in funds} == {"ATR-CASH", "ATR-INC", "ATR-BAL", "ATR-GRW", "ATR-GLB", "ATR-DIV", "ATR-TEC"}
    for f in funds:
        assert sum(c.weight for c in f.constituents) == Decimal("1.0000")
    assert len(seed_funds(db)) == 7  # idempotent
    assert len(db.scalars(select(Fund)).all()) == 7


def test_build_nav_series_is_daily_rebalanced_weighted_index():
    prices = pd.DataFrame(
        {"A": [100.0, 110.0, 121.0], "B": [100.0, 90.0, 81.0]},
        index=pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"]),
    )
    nav = build_nav_series(prices, {"A": 0.5, "B": 0.5})
    assert list(nav.round(6)) == [100.0, 100.0, 100.0]  # +10% and -10% at equal weight cancel
    nav2 = build_nav_series(prices, {"A": 1.0})
    assert list(nav2.round(6)) == [100.0, 110.0, 121.0]


def test_publish_latest_and_guard(db):
    seed_funds(db)
    nav = pd.Series([100.0, 101.5], index=pd.to_datetime(["2026-01-02", "2026-01-05"]))
    n = publish_prices(db, "ATR-BAL", nav, Decimal("1000000"))
    db.commit()
    assert n == 2
    p = latest_price(db, "ATR-BAL", date(2026, 1, 4))  # Sunday: falls back to Friday
    assert p is not None and p.as_of == date(2026, 1, 2) and p.nav == Decimal("100.000000")
    assert latest_price(db, "ATR-BAL", date(2026, 1, 1)) is None
    missing = pricing_guard(db, date(2026, 1, 5))
    assert "ATR-BAL" not in missing and len(missing) == 6
    assert publish_prices(db, "ATR-BAL", nav, Decimal("1000000")) == 2  # re-publish is an upsert
    assert len(db.scalars(select(Price).where(Price.fund_code == "ATR-BAL")).all()) == 2
