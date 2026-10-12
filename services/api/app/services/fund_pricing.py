"""Daily fund pricing with a checker (blueprint D3).

The day-end job drafts each house fund's NAV for the last closed session: the previous published NAV moved by the
basket's weighted return over its constituents' closes. Every draft carries checks (a large move, a long gap since the
last price). An operations person reviews them and asks for publication; a second person approves with a one-time code
(D6). Publishing makes the prices live and runs the allocation for that dealing day.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.events import emit
from app.markets.quotes import NEW_YORK, is_trading_day
from app.markets.universe import load_market_daily
from app.models import Approval, Fund, Person, Posting, Price
from app.services.allocation import allocate
from app.services.approvals import ApprovalError, OpsError, request_approval
from app.services.pricing import latest_price

log = logging.getLogger(__name__)
NAV_Q = Decimal("0.000001")
MOVE_LIMIT_PCT = 5.0
MAX_GAP_DAYS = 7
CLOSES_READY = time(16, 15)  # New York: closing prices are settled a few minutes after the bell


class PricingError(OpsError):
    pass


@dataclass(frozen=True)
class PriceCheck:
    code: str
    ok: bool
    detail: str


@dataclass
class DraftView:
    fund_code: str
    name: str
    as_of: date
    prev_as_of: date | None
    prev_nav: Decimal | None
    nav: Decimal
    move_pct: float
    status: str
    checks: list[PriceCheck]


def last_closed_session(now: datetime) -> date:
    local = now.astimezone(NEW_YORK)
    day = local.date()
    if is_trading_day(day) and local.time() >= CLOSES_READY:
        return day
    day -= timedelta(days=1)
    while not is_trading_day(day):
        day -= timedelta(days=1)
    return day


def constituent_closes(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    """Daily closes from the live market-data provider, falling back to the committed daily closes."""
    try:
        from app.services.market_data import get_market_data

        return get_market_data(get_settings()).history(tickers, start, end)
    except Exception as e:  # unreachable provider: price from what was committed (older, but real)
        log.warning("live closes unavailable (%s); using the committed daily closes", e)
        daily = load_market_daily()
        return daily.loc[pd.Timestamp(start):pd.Timestamp(end), [t for t in tickers if t in daily.columns]]


def _close(frame: pd.DataFrame, ticker: str, day: date) -> float:
    value = frame[ticker].get(pd.Timestamp(day)) if ticker in frame.columns else None
    if value is None or pd.isna(value):
        raise KeyError(f"no close for {ticker} on {day}")
    return float(value)


def units_outstanding(db: Session, fund_code: str) -> Decimal:
    return db.scalar(select(func.coalesce(func.sum(Posting.units), 0)).where(Posting.instrument == fund_code)) \
        or Decimal("0")


def draft_prices(db: Session, as_of: date, closes: pd.DataFrame | None = None) -> tuple[list[Price], list[str]]:
    """Draft a price for every house fund that has none on `as_of`. Returns the drafts and the funds it could not
    price (no previous price, or no close for a constituent)."""
    funds = db.scalars(select(Fund).order_by(Fund.code)).all()
    todo = [f for f in funds
            if db.scalar(select(Price.id).where(Price.fund_code == f.code, Price.as_of == as_of)) is None]
    if not todo:
        return [], []
    previous = {f.code: latest_price(db, f.code, as_of - timedelta(days=1)) for f in todo}
    known = [p.as_of for p in previous.values() if p is not None]
    if not known:
        return [], [f.code for f in todo]
    if closes is None:
        tickers = sorted({c.ticker for f in todo for c in f.constituents})
        closes = constituent_closes(tickers, min(known), as_of)
    closes = closes.copy()
    closes.index = pd.to_datetime(closes.index).normalize()
    made, skipped = [], []
    for fund in todo:
        prev = previous[fund.code]
        try:
            if prev is None:
                raise KeyError("no previous published price")
            ret = sum(float(c.weight) * (_close(closes, c.ticker, as_of) / _close(closes, c.ticker, prev.as_of) - 1)
                      for c in fund.constituents)
        except KeyError as e:
            log.info("cannot draft %s for %s: %s", fund.code, as_of, e)
            skipped.append(fund.code)
            continue
        nav = (prev.nav * Decimal(str(1 + ret))).quantize(NAV_Q, rounding=ROUND_HALF_EVEN)
        row = Price(fund_code=fund.code, as_of=as_of, nav=nav, units_in_issue=units_outstanding(db, fund.code),
                    status="draft")
        db.add(row)
        made.append(row)
    db.flush()
    return made, skipped


def price_checks(db: Session, as_of: date) -> list[DraftView]:
    rows = db.scalars(select(Price).where(Price.as_of == as_of, Price.status.in_(("draft", "checked")))
                      .order_by(Price.fund_code)).all()
    names = {f.code: f.name for f in db.scalars(select(Fund)).all()}
    out: list[DraftView] = []
    for row in rows:
        prev = latest_price(db, row.fund_code, as_of - timedelta(days=1))
        move = round((float(row.nav) / float(prev.nav) - 1) * 100, 2) if prev else 0.0
        checks = [PriceCheck("MOVE", abs(move) <= MOVE_LIMIT_PCT,
                             f"Moved {move:+.1f}% since the last published price"
                             + ("." if abs(move) <= MOVE_LIMIT_PCT
                                else f", beyond the {MOVE_LIMIT_PCT:.0f}% check: confirm it against the market."))]
        if prev is not None:
            gap = (as_of - prev.as_of).days
            checks.append(PriceCheck("GAP", gap <= MAX_GAP_DAYS,
                                     f"The last published price was {gap} day{'s' if gap != 1 else ''} earlier"
                                     + ("." if gap <= MAX_GAP_DAYS else ": prices were missed in between.")))
        out.append(DraftView(fund_code=row.fund_code, name=names[row.fund_code], as_of=as_of,
                             prev_as_of=prev.as_of if prev else None, prev_nav=prev.nav if prev else None,
                             nav=row.nav, move_pct=move, status=row.status, checks=checks))
    return out


def request_publish(db: Session, as_of: date, requester: Person, reason: str) -> Approval:
    views = price_checks(db, as_of)
    if not views:
        raise PricingError(f"No draft prices for {as_of:%B} {as_of.day} to publish.")
    approval = request_approval(
        db, action="publish_prices", payload={"as_of": as_of.isoformat(),
                                              "prices": {v.fund_code: str(v.nav) for v in views}},
        summary=f"Publish {len(views)} fund price{'s' if len(views) != 1 else ''} for {as_of:%B} {as_of.day}",
        reason=reason,
        evidence=[{"label": v.name, "detail": " ".join(c.detail for c in v.checks)} for v in views],
        requested_by=requester)
    for row in db.scalars(select(Price).where(Price.as_of == as_of, Price.status == "draft")).all():
        row.status = "checked"
    db.flush()
    return approval


def execute_publish(db: Session, approval: Approval, approver: Person, now: datetime) -> dict:
    as_of = date.fromisoformat(approval.payload["as_of"])
    wanted = approval.payload["prices"]
    rows = {p.fund_code: p for p in db.scalars(select(Price).where(
        Price.as_of == as_of, Price.status.in_(("draft", "checked")))).all()}
    if set(rows) != set(wanted) or any(str(rows[c].nav) != nav for c, nav in wanted.items()):
        raise ApprovalError("The draft prices changed after the request; ask for publication again.")
    for code, row in rows.items():
        row.status, row.published_at = "published", now
        emit("PricePublished", {"fund_code": code, "as_of": as_of.isoformat(), "nav": f"{row.nav:.6f}",
                                "approval_id": approval.id})
    db.flush()
    report = allocate(db, as_of, now)
    return {"as_of": as_of.isoformat(), "published": len(rows), "allocation": report.as_dict()}
