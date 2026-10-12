"""Orders (C2): preview with the Guardian, place, hold for an advisor, release, reject, cancel and fill.

Nothing reaches the ledger until a broker reports a fill. A fill writes two postings that share the order id as their
reference: the shares (with the trade's cash on that posting) and the paper cash that paid for them or came back.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import emit
from app.markets.broker import Broker, BrokerOrder, Execution, get_broker
from app.markets.quotes import CommittedQuotes, Quote, get_quotes, market_session
from app.markets.universe import CASH, instrument
from app.models import Account, Person, TradeOrder
from app.models.base import utcnow
from app.services.account_snapshot import account_snapshot
from app.services.devices import see_device
from app.services.guardian import GuardianReport, OrderRequest, assess, report_json, usd
from app.services.ledger import InsufficientUnits, apply_posting, q_cash

PENDING = ("held", "open")
ACKNOWLEDGE = "Read the Guardian's warnings and confirm them before placing this order."
VERDICT_WORDS = {"proceed": "proceed", "warn": "proceed with care", "hold": "hold for an advisor", "block": "blocked"}


class OrderError(Exception):
    """The order cannot go ahead; the message says why, in words the person can act on."""


def describe(o: TradeOrder) -> str:
    verb = "Buy" if o.side == "buy" else "Sell"
    how = "at market" if o.order_type == "market" else f"with a limit of {usd(o.limit_price)}"
    return f"{verb} {o.quantity} {o.symbol} {how}"


def _step(o: TradeOrder, state: str, note: str, now: datetime) -> None:
    o.timeline = [*(o.timeline or []), {"state": state, "note": note, "at": now.isoformat()}]


def _broker_order(o: TradeOrder) -> BrokerOrder:
    inst = instrument(o.symbol)
    return BrokerOrder(o.symbol, o.side, o.order_type, o.quantity, o.limit_price, inst.kind if inst else "stock", o.id)


def preview_order(db: Session, account: Account, req: OrderRequest, *, device_hash: str | None = None,
                  device_label: str = "", now: datetime | None = None, quotes: CommittedQuotes | None = None,
                  record_device: bool = True, exclude_order: str | None = None) -> GuardianReport:
    now = now or utcnow()
    quotes = quotes or get_quotes()
    inst = instrument(req.symbol)
    if inst is None:
        raise OrderError(f"{req.symbol} is not in Atrium's trading list.")
    quote = quotes.quote(inst.symbol)
    if quote is None:
        raise OrderError(f"There is no price for {inst.symbol} right now.")
    snap = account_snapshot(db, account, device_hash=device_hash, now=now, quotes=quotes, exclude_order=exclude_order)
    report = assess(snap, OrderRequest(inst.symbol, req.side, req.order_type, req.quantity, req.limit_price), inst,
                    quote, market_session(now))
    if record_device and device_hash:
        see_device(db, account.id, device_hash, device_label, now)
    return report


def place_order(db: Session, account: Account, req: OrderRequest, *, acknowledge: bool = False,
                device_hash: str | None = None, device_label: str = "", now: datetime | None = None,
                quotes: CommittedQuotes | None = None, broker: Broker | None = None) -> TradeOrder:
    now = now or utcnow()
    broker = broker or get_broker()
    report = preview_order(db, account, req, device_hash=device_hash, device_label=device_label, now=now,
                           quotes=quotes)
    verdict = report.verdict
    if verdict == "block":
        raise OrderError(next(c.detail for c in report.checks if c.outcome == "block"))
    if verdict == "warn" and not acknowledge:
        raise OrderError(ACKNOWLEDGE)
    order = TradeOrder(account_id=account.id, symbol=report.order.symbol, side=req.side, order_type=req.order_type,
                       quantity=req.quantity, limit_price=req.limit_price, state="held" if verdict == "hold" else "open",
                       verdict=verdict, guardian=report_json(report), acknowledged_warnings=verdict == "warn",
                       estimated_value=report.estimate.value, broker=broker.name, trust_score=report.trust.score,
                       trust_band=report.trust.band, device_hash=device_hash, timeline=[], created_at=now)
    db.add(order)
    db.flush()
    _step(order, "placed", f"{describe(order)}. The Guardian's verdict: {VERDICT_WORDS[verdict]}.", now)
    emit("OrderPlaced", {"order_id": order.id, "account_id": account.id, "symbol": order.symbol, "side": order.side,
                         "quantity": order.quantity, "verdict": verdict, "trust_score": order.trust_score})
    if report.trust.band != "clear":
        emit("TrustScoreChanged", {"account_id": account.id, "stage": "trading", "score": report.trust.score,
                                   "band": report.trust.band, "signals": [s.code for s in report.trust.signals]})
    if verdict == "hold":
        reasons = "; ".join(c.title.lower() for c in report.checks if c.outcome == "hold")
        _step(order, "held", f"Held for an advisor: {reasons}.", now)
        emit("OrderHeld", {"order_id": order.id, "account_id": account.id, "reasons": reasons})
        return order
    _execute(db, order, report.quote, report.session.is_open, broker, now)
    return order


def _execute(db: Session, order: TradeOrder, quote: Quote, market_open: bool, broker: Broker, now: datetime) -> None:
    result = broker.submit(_broker_order(order), quote, market_open)
    order.broker, order.broker_order_id = broker.name, result.broker_order_id
    _apply(db, order, result, now)


def _apply(db: Session, order: TradeOrder, result: Execution, now: datetime) -> None:
    if result.status == "filled":
        try:
            _fill(db, order, result.price, now, result.note)
        except InsufficientUnits:
            order.state = "rejected"
            _step(order, "rejected", "Not enough paper cash or shares when the order came to fill.", now)
            emit("OrderRejected", {"order_id": order.id, "account_id": order.account_id, "by": "ledger"})
    elif result.status == "open":
        if order.state != "open" or order.timeline[-1]["state"] != "open":
            order.state = "open"
            _step(order, "open", result.note, now)
    else:
        order.state = "rejected"
        _step(order, "rejected", result.note, now)
        emit("OrderRejected", {"order_id": order.id, "account_id": order.account_id, "by": "broker"})


def _fill(db: Session, order: TradeOrder, price: Decimal, now: datetime, note: str) -> None:
    gross = q_cash(price * order.quantity)
    sign = 1 if order.side == "buy" else -1
    shares = dict(instrument=order.symbol, instrument_type="equity", units=Decimal(sign * order.quantity),
                  cash=-sign * gross, price=price)
    money = dict(instrument=CASH, instrument_type="cash", units=-sign * gross, cash=Decimal("0"), price=Decimal("1"))
    # The leg that spends goes first (cash for a purchase, shares for a sale): if the account cannot cover it,
    # apply_posting raises before anything is written.
    for leg in ((money, shares) if order.side == "buy" else (shares, money)):
        apply_posting(db, account_id=order.account_id, posting_type=order.side, value_date=now.date(),
                      reference=order.id, **leg)
    order.state, order.fill_price, order.filled_at = "filled", price, now
    _step(order, "filled", note, now)
    emit("OrderFilled", {"order_id": order.id, "account_id": order.account_id, "symbol": order.symbol,
                         "side": order.side, "quantity": order.quantity, "price": str(price), "broker": order.broker})
    emit("TransactionPosted", {"account_id": order.account_id, "reference": order.id, "instrument": order.symbol,
                               "units": str(sign * order.quantity), "cash": str(-sign * gross)})


def release_order(db: Session, order: TradeOrder, advisor: Person, note: str = "", *, now: datetime | None = None,
                  quotes: CommittedQuotes | None = None, broker: Broker | None = None) -> TradeOrder:
    now = now or utcnow()
    if order.state != "held":
        raise OrderError("Only an order waiting for an advisor can be released.")
    account = db.get(Account, order.account_id)
    req = OrderRequest(order.symbol, order.side, order.order_type, order.quantity, order.limit_price)
    report = preview_order(db, account, req, now=now, quotes=quotes, record_device=False, exclude_order=order.id)
    blocked = [c for c in report.checks if c.outcome == "block"]
    if blocked:
        raise OrderError(f"This order can no longer go ahead: {blocked[0].detail}")
    order.reviewed_by, order.reviewed_at, order.review_note = advisor.id, now, note or None
    _step(order, "released", f"Released by {advisor.full_name}" + (f": {note}" if note else "."), now)
    emit("OrderReleased", {"order_id": order.id, "account_id": order.account_id, "by": advisor.id})
    _execute(db, order, report.quote, report.session.is_open, broker or get_broker(), now)
    return order


def reject_order(db: Session, order: TradeOrder, advisor: Person, note: str = "", *,
                 now: datetime | None = None) -> TradeOrder:
    now = now or utcnow()
    if order.state != "held":
        raise OrderError("Only an order waiting for an advisor can be rejected.")
    order.state = "rejected"
    order.reviewed_by, order.reviewed_at, order.review_note = advisor.id, now, note or None
    _step(order, "rejected", f"Rejected by {advisor.full_name}" + (f": {note}" if note else "."), now)
    emit("OrderRejected", {"order_id": order.id, "account_id": order.account_id, "by": advisor.id})
    return order


def cancel_order(db: Session, order: TradeOrder, *, now: datetime | None = None,
                 broker: Broker | None = None) -> TradeOrder:
    now = now or utcnow()
    if order.state not in PENDING:
        raise OrderError("Only an order that is still waiting can be cancelled.")
    if order.state == "open" and order.broker_order_id:
        (broker or get_broker()).cancel(order.broker_order_id)
    order.state = "cancelled"
    _step(order, "cancelled", "Cancelled by the account holder.", now)
    emit("OrderCancelled", {"order_id": order.id, "account_id": order.account_id})
    return order


def refresh_orders(db: Session, account_id: str, *, now: datetime | None = None,
                   quotes: CommittedQuotes | None = None, broker: Broker | None = None) -> int:
    """Ask the broker about every resting order on the account; returns how many filled."""
    now = now or utcnow()
    quotes = quotes or get_quotes()
    broker = broker or get_broker()
    filled = 0
    rows = db.scalars(select(TradeOrder).where(TradeOrder.account_id == account_id, TradeOrder.state == "open",
                                               TradeOrder.broker == broker.name)).all()
    for order in rows:
        quote = quotes.quote(order.symbol)
        if quote is None:
            continue
        _apply(db, order, broker.check(_broker_order(order), order.broker_order_id, quote), now)
        filled += order.state == "filled"
    return filled
