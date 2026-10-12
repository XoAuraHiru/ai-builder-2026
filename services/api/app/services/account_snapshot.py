"""Everything the Guardian needs to know about an account, read once before it judges an order.

That is: what the account holds and what it is worth; cash and shares already promised to held and resting orders;
sales and purchases in the last 30 days (wash sales); same-day round trips in the last five trading days (day trading);
and the inputs to the account's trust score.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.markets.quotes import CommittedQuotes, get_quotes, is_trading_day
from app.models import Account, Fund, Instruction, LeadConversion, Posting, TradeOrder
from app.models.base import utcnow
from app.services.account_trust import RAPID_WINDOW, TrustInputs
from app.services.analytics import universe, weights_of
from app.services.devices import aware, first_seen
from app.services.instructions import LotView, free_lots, open_lots
from app.services.ledger import q_cash
from app.services.portfolio import PortfolioView, valuation

PENDING = ("held", "open")
WASH_SALE_DAYS = 30
DAY_TRADE_DAYS = 5  # trading days


@dataclass(frozen=True)
class Sale:
    symbol: str
    day: date
    gain: Decimal  # negative for a loss


@dataclass
class AccountSnapshot:
    account_id: str
    profile_band: int | None
    view: PortfolioView
    funds: dict[str, Fund]
    cash: Decimal
    reserved_cash: Decimal
    units: dict[str, Decimal]
    reserved_units: dict[str, Decimal]
    lots: dict[str, list[LotView]]
    sales: list[Sale]
    buys: list[tuple[str, date]]
    traded_today: dict[str, set[str]]
    day_trades: int
    trust: TrustInputs
    today: date

    @property
    def cash_free(self) -> Decimal:
        return q_cash(self.cash - self.reserved_cash)

    def units_free(self, symbol: str) -> Decimal:
        return self.units.get(symbol, Decimal("0")) - self.reserved_units.get(symbol, Decimal("0"))

    @property
    def traded_value(self) -> Decimal:
        return sum((h.value for h in self.view.holdings if h.kind in ("stock", "etf")), Decimal("0"))

    @property
    def weights(self) -> dict[str, float]:
        return weights_of(self.view)


def trading_days_back(today: date, n: int) -> date:
    """The first of the last `n` trading days, counting today if it is one."""
    day, counted = today, 0
    while True:
        if is_trading_day(day):
            counted += 1
            if counted == n:
                return day
        day -= timedelta(days=1)


def trust_inputs(db: Session, account: Account, device_hash: str | None, now: datetime) -> TrustInputs:
    baseline = db.scalar(select(LeadConversion.trust_score).where(LeadConversion.account_id == account.id)
                         .order_by(LeadConversion.created_at.desc()).limit(1))
    last_order = db.scalar(select(func.max(TradeOrder.created_at)).where(TradeOrder.account_id == account.id))
    last_instruction = db.scalar(select(func.max(Instruction.requested_at))
                                 .where(Instruction.account_id == account.id))
    moments = [aware(m) for m in (last_order, last_instruction) if m is not None]
    recent = db.scalar(select(func.count()).select_from(TradeOrder).where(
        TradeOrder.account_id == account.id, TradeOrder.created_at >= now - RAPID_WINDOW)) or 0
    return TrustInputs(
        baseline=baseline if baseline is not None else 100,
        baseline_source="the lead's trust score at conversion" if baseline is not None else "no earlier score",
        device_sent=device_hash is not None,
        device_first_seen=first_seen(db, account.id, device_hash) if device_hash else None,
        last_activity=max(moments) if moments else None, recent_orders=recent, now=now)


def account_snapshot(db: Session, account: Account, *, device_hash: str | None, now: datetime | None = None,
                     quotes: CommittedQuotes | None = None, exclude_order: str | None = None) -> AccountSnapshot:
    """`exclude_order` leaves one waiting order's reservation out: an advisor releasing it checks the account without
    it."""
    now = now or utcnow()
    today = now.date()
    view = valuation(db, account.id, today, quotes or get_quotes())
    pending = [o for o in db.scalars(select(TradeOrder).where(TradeOrder.account_id == account.id,
                                                              TradeOrder.state.in_(PENDING))).all()
               if o.id != exclude_order]
    reserved_cash = sum((o.estimated_value for o in pending if o.side == "buy"), Decimal("0"))
    reserved_units: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for o in pending:
        if o.side == "sell":
            reserved_units[o.symbol] += o.quantity
    units = {h.instrument: h.units for h in view.holdings if h.kind in ("stock", "etf")}
    lots = {s: free_lots(open_lots(db, account.id, s), reserved_units.get(s, Decimal("0"))) for s in units}

    window = trading_days_back(today, DAY_TRADE_DAYS)
    wash_from = today - timedelta(days=WASH_SALE_DAYS)
    postings = db.scalars(select(Posting).where(Posting.account_id == account.id, Posting.instrument_type == "equity",
                                                Posting.value_date >= min(window, wash_from))).all()
    sales = [Sale(p.instrument, p.value_date, q_cash(p.cash - (p.realised_cost or Decimal("0"))))
             for p in postings if p.posting_type == "sell" and p.value_date >= wash_from]
    buys = [(p.instrument, p.value_date) for p in postings if p.posting_type == "buy" and p.value_date >= wash_from]
    sides: dict[tuple[str, date], set[str]] = defaultdict(set)
    for p in postings:
        if p.posting_type in ("buy", "sell"):
            sides[(p.instrument, p.value_date)].add(p.posting_type)
    day_trades = sum(1 for (_, day), s in sides.items() if day >= window and s == {"buy", "sell"})
    traded_today = {symbol: s for (symbol, day), s in sides.items() if day == today}
    return AccountSnapshot(account_id=account.id, profile_band=account.person.risk_band, view=view,
                           funds=universe(db), cash=view.cash, reserved_cash=q_cash(reserved_cash), units=units,
                           reserved_units=dict(reserved_units), lots=lots, sales=sales, buys=buys,
                           traded_today=traded_today, day_trades=day_trades,
                           trust=trust_inputs(db, account, device_hash, now), today=today)
