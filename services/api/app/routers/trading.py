"""Orders with the Pre-trade Guardian (C2–C4).

The account holder previews, asks for an explanation, places, lists and cancels. Advisors work the held queue: they ask
Gemini Pro for a review note, then release or reject. Releasing is a person's decision; the note only suggests.
"""
from collections.abc import Callable
from decimal import Decimal
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm import LLM, LLMError, get_llm
from app.auth import CurrentUser, assert_account_access, get_current_user, require_roles
from app.db import get_db
from app.governance.breakers import BreakerOpen
from app.markets.broker import Broker, broker_dep
from app.markets.quotes import CommittedQuotes, quote_book
from app.markets.universe import CASH, instrument
from app.models import Account, Person, TradeOrder
from app.routers.accounts import account_or_404
from app.routers.invest import EXPLAIN_BUSY
from app.schemas.trading import DecisionIn, ExplainedOrder, GuardianOut, OrderIn, OrderOut, OrdersOut
from app.services.devices import device_hash, device_label
from app.services.guardian import OrderRequest, report_json
from app.services.ledger import balance, q_cash
from app.services.order_ai import explain_order, write_review_note
from app.services.orders import (PENDING, OrderError, cancel_order, place_order, preview_order, refresh_orders,
                                 reject_order, release_order)
from app.services.portfolio import PriceUnavailable

router = APIRouter(prefix="/accounts", tags=["trading"])
staff_router = APIRouter(prefix="/orders", tags=["trading"])
staff = require_roles("staff")
REVIEW_BUSY = "The review note is unavailable right now; please try again in a minute."
T = TypeVar("T")


def _guarded(action: Callable[[], T]) -> T:
    try:
        return action()
    except OrderError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except PriceUnavailable as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


def _device(request: Request) -> tuple[str | None, str]:
    return device_hash(request.headers.get("X-Device-Id")), device_label(request.headers.get("User-Agent"))


def _account(db: Session, account_id: str, user: CurrentUser, *, holder_only: str = "") -> Account:
    account = account_or_404(db, account_id)
    assert_account_access(user, account)
    if holder_only and account.person_id != user.person_id:
        raise HTTPException(status_code=403, detail=holder_only)
    return account


def _holder(account: Account, user: CurrentUser) -> bool:
    """Only the account holder's browser is recorded as one of the account's devices; staff looking at a client's
    order must not make their own browser "known" on the client's account."""
    return account.person_id == user.person_id


def _request(body: OrderIn) -> OrderRequest:
    return OrderRequest(body.symbol.strip().upper(), body.side, body.order_type, body.quantity,
                        body.limit_price if body.order_type == "limit" else None)


def order_out(db: Session, o: TradeOrder) -> OrderOut:
    account = db.get(Account, o.account_id)
    inst = instrument(o.symbol)
    reviewer = db.get(Person, o.reviewed_by) if o.reviewed_by else None
    return OrderOut(
        id=o.id, account_id=o.account_id, account_number=account.number, client_name=account.person.full_name,
        symbol=o.symbol, name=inst.name if inst else o.symbol, side=o.side, order_type=o.order_type,
        quantity=o.quantity, limit_price=o.limit_price, state=o.state, verdict=o.verdict,
        acknowledged_warnings=o.acknowledged_warnings, estimated_value=o.estimated_value, fill_price=o.fill_price,
        filled_at=o.filled_at, broker=o.broker, trust_score=o.trust_score, trust_band=o.trust_band,
        created_at=o.created_at, timeline=o.timeline or [], guardian=o.guardian, review_note=o.review_note,
        reviewed_by_name=reviewer.full_name if reviewer else None, ai_review=o.ai_review)


@router.post("/{account_id}/orders/preview", response_model=GuardianOut)
def preview(account_id: str, body: OrderIn, request: Request, db: Session = Depends(get_db),
            quotes: CommittedQuotes = Depends(quote_book), user: CurrentUser = Depends(get_current_user)):
    account = _account(db, account_id, user)
    hashed, label = _device(request)
    report = _guarded(lambda: preview_order(db, account, _request(body), device_hash=hashed, device_label=label,
                                            quotes=quotes, record_device=_holder(account, user)))
    db.commit()  # the device sighting
    return report_json(report)


@router.post("/{account_id}/orders/explain", response_model=ExplainedOrder)
def explain(account_id: str, body: OrderIn, request: Request, db: Session = Depends(get_db),
            quotes: CommittedQuotes = Depends(quote_book), llm: LLM = Depends(get_llm),
            user: CurrentUser = Depends(get_current_user)):
    account = _account(db, account_id, user)
    hashed, label = _device(request)
    report = report_json(_guarded(lambda: preview_order(db, account, _request(body), device_hash=hashed,
                                                        device_label=label, quotes=quotes,
                                                        record_device=_holder(account, user))))
    try:
        narrative = explain_order(db, llm, account, report)
    except LLMError as e:
        raise HTTPException(status_code=503, detail=EXPLAIN_BUSY) from e
    db.commit()
    return {"report": report, "narrative": narrative}


@router.post("/{account_id}/orders", response_model=OrderOut, status_code=201)
def place(account_id: str, body: OrderIn, request: Request, db: Session = Depends(get_db),
          quotes: CommittedQuotes = Depends(quote_book), broker: Broker = Depends(broker_dep),
          user: CurrentUser = Depends(get_current_user)):
    account = _account(db, account_id, user, holder_only="Only the account holder can place orders.")
    hashed, label = _device(request)
    order = _guarded(lambda: place_order(db, account, _request(body), acknowledge=body.acknowledge_warnings,
                                         device_hash=hashed, device_label=label, quotes=quotes, broker=broker))
    db.commit()
    return order_out(db, order)


@router.get("/{account_id}/orders", response_model=OrdersOut)
def list_orders(account_id: str, db: Session = Depends(get_db), quotes: CommittedQuotes = Depends(quote_book),
                broker: Broker = Depends(broker_dep), user: CurrentUser = Depends(get_current_user)):
    account = _account(db, account_id, user)
    refresh_orders(db, account.id, quotes=quotes, broker=broker)
    db.commit()
    rows = db.scalars(select(TradeOrder).where(TradeOrder.account_id == account.id)
                      .order_by(TradeOrder.created_at.desc()).limit(100)).all()
    waiting = db.scalars(select(TradeOrder.estimated_value).where(
        TradeOrder.account_id == account.id, TradeOrder.state.in_(PENDING), TradeOrder.side == "buy")).all()
    cash = q_cash(balance(db, account.id, CASH))
    return OrdersOut(cash=cash, cash_free=q_cash(cash - sum(waiting, Decimal("0"))),
                     orders=[order_out(db, o) for o in rows])


@router.post("/{account_id}/orders/{order_id}/cancel", response_model=OrderOut)
def cancel(account_id: str, order_id: str, db: Session = Depends(get_db), broker: Broker = Depends(broker_dep),
           user: CurrentUser = Depends(get_current_user)):
    account = _account(db, account_id, user, holder_only="Only the account holder can cancel orders.")
    order = db.get(TradeOrder, order_id)
    if order is None or order.account_id != account.id:
        raise HTTPException(status_code=404, detail="That order was not found on this account.")
    _guarded(lambda: cancel_order(db, order, broker=broker))
    db.commit()
    return order_out(db, order)


def _order_or_404(db: Session, order_id: str) -> TradeOrder:
    order = db.get(TradeOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="That order was not found.")
    return order


@staff_router.get("/held", response_model=list[OrderOut])
def held(db: Session = Depends(get_db), user: CurrentUser = Depends(staff)):
    rows = db.scalars(select(TradeOrder).where(TradeOrder.state == "held").order_by(TradeOrder.created_at)).all()
    return [order_out(db, o) for o in rows]


@staff_router.post("/{order_id}/release", response_model=OrderOut)
def release(order_id: str, body: DecisionIn, db: Session = Depends(get_db),
            quotes: CommittedQuotes = Depends(quote_book), broker: Broker = Depends(broker_dep),
            user: CurrentUser = Depends(staff)):
    order = _order_or_404(db, order_id)
    advisor = db.get(Person, user.person_id)
    _guarded(lambda: release_order(db, order, advisor, body.note.strip(), quotes=quotes, broker=broker))
    db.commit()
    return order_out(db, order)


@staff_router.post("/{order_id}/reject", response_model=OrderOut)
def reject(order_id: str, body: DecisionIn, db: Session = Depends(get_db), user: CurrentUser = Depends(staff)):
    order = _order_or_404(db, order_id)
    advisor = db.get(Person, user.person_id)
    _guarded(lambda: reject_order(db, order, advisor, body.note.strip()))
    db.commit()
    return order_out(db, order)


@staff_router.post("/{order_id}/review-note", response_model=OrderOut)
def review_note(order_id: str, db: Session = Depends(get_db), llm: LLM = Depends(get_llm),
                user: CurrentUser = Depends(staff)):
    order = _order_or_404(db, order_id)
    if order.state != "held":
        raise HTTPException(status_code=409, detail="Only an order waiting for an advisor gets a review note.")
    try:
        write_review_note(db, llm, order)
    except BreakerOpen as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except LLMError as e:
        raise HTTPException(status_code=503, detail=REVIEW_BUSY) from e
    db.commit()
    return order_out(db, order)
