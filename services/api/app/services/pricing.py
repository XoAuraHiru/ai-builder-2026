from datetime import date
from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import emit
from app.models import Fund, Price
from app.models.base import utcnow


def build_nav_series(prices: pd.DataFrame, weights: dict[str, float], base: float = 100.0) -> pd.Series:
    """NAV per unit of a fixed-weight, daily-rebalanced basket, starting at `base` on the first date.

    `prices` has one column per ticker (adjusted close) and a DatetimeIndex. Rows with any
    missing constituent are dropped so the series is only defined where every leg has a price.
    """
    cols = list(weights)
    px = prices[cols].dropna()
    if px.empty:
        raise ValueError("no overlapping price history for " + ", ".join(cols))
    w = pd.Series(weights, dtype="float64")
    daily = px.pct_change().fillna(0.0)
    basket = (daily * w).sum(axis=1)
    nav = (1.0 + basket).cumprod() * base
    nav.name = "nav"
    return nav


def publish_prices(db: Session, fund_code: str, nav: pd.Series, units_in_issue: Decimal) -> int:
    """Upsert published prices for every date in `nav`. Returns the number of rows written."""
    existing = {p.as_of: p for p in db.scalars(select(Price).where(Price.fund_code == fund_code)).all()}
    n = 0
    for ts, value in nav.items():
        as_of = ts.date() if hasattr(ts, "date") else ts
        row = existing.get(as_of)
        if row is None:
            row = Price(fund_code=fund_code, as_of=as_of)
            db.add(row)
        row.nav = Decimal(str(round(float(value), 6)))
        row.units_in_issue = Decimal(units_in_issue)
        row.status = "published"
        row.published_at = utcnow()
        n += 1
        emit("PricePublished", {"fund_code": fund_code, "as_of": as_of.isoformat(), "nav": f"{row.nav:.6f}"})
    db.flush()
    return n


def latest_price(db: Session, fund_code: str, as_of: date) -> Price | None:
    return db.scalar(
        select(Price)
        .where(Price.fund_code == fund_code, Price.status == "published", Price.as_of <= as_of)
        .order_by(Price.as_of.desc())
        .limit(1)
    )


def pricing_guard(db: Session, as_of: date) -> list[str]:
    """Fund codes with no published price on `as_of`. Non-empty means allocations must wait."""
    priced = set(db.scalars(select(Price.fund_code).where(Price.as_of == as_of, Price.status == "published")).all())
    return [code for code in db.scalars(select(Fund.code).order_by(Fund.code)).all() if code not in priced]
