"""Markets and watchlists (C1)."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.db import get_db
from app.markets.quotes import CommittedQuotes, market_session, quote_book
from app.markets.universe import instrument, instruments
from app.models import WatchItem
from app.models.base import utcnow
from app.schemas.trading import MarketDetailOut, MarketRow, MarketsOut, PricePoint, quote_out, session_out

router = APIRouter(tags=["markets"])


def _watched(db: Session, user: CurrentUser) -> set[str]:
    if not user.person_id:
        return set()
    return set(db.scalars(select(WatchItem.symbol).where(WatchItem.person_id == user.person_id)).all())


def _not_listed(symbol: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{symbol.strip().upper()} is not in Atrium's trading list.")


@router.get("/markets", response_model=MarketsOut)
def markets(db: Session = Depends(get_db), quotes: CommittedQuotes = Depends(quote_book),
            user: CurrentUser = Depends(get_current_user)):
    watched = _watched(db, user)
    rows, latest = [], None
    for symbol, i in instruments().items():
        q = quotes.quote(symbol)
        if q is None:
            continue
        latest = q.as_of if latest is None else max(latest, q.as_of)
        rows.append(MarketRow(symbol=symbol, name=i.name, kind=i.kind, sector=i.sector_label, risk_band=i.risk_band,
                              price=q.price, change_pct=q.change_pct, source=q.source, watched=symbol in watched))
    return MarketsOut(session=session_out(market_session(utcnow())), as_of=latest, rows=rows)


@router.get("/markets/{symbol}", response_model=MarketDetailOut)
def market(symbol: str, db: Session = Depends(get_db), quotes: CommittedQuotes = Depends(quote_book),
           user: CurrentUser = Depends(get_current_user)):
    i = instrument(symbol)
    if i is None:
        raise _not_listed(symbol)
    q = quotes.quote(i.symbol)
    if q is None:
        raise HTTPException(status_code=409, detail=f"There is no price for {i.symbol} right now.")
    history = quotes.history(i.symbol)
    return MarketDetailOut(
        symbol=i.symbol, name=i.name, kind=i.kind, sector=i.sector_label, industry=i.industry, summary=i.summary,
        risk_band=i.risk_band, volatility_pct=i.volatility_pct, market_value=i.market_value, avg_volume=i.avg_volume,
        quote=quote_out(q), session=session_out(market_session(utcnow())),
        history=[PricePoint(day=ts.date(), close=round(float(v), 4)) for ts, v in history.items()],
        watched=i.symbol in _watched(db, user))


def _person(user: CurrentUser) -> str:
    if not user.person_id:
        raise HTTPException(status_code=403, detail="Only a registered person has a watchlist.")
    return user.person_id


@router.get("/me/watchlist", response_model=list[str])
def watchlist(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    return sorted(_watched(db, user))


@router.put("/me/watchlist/{symbol}", status_code=204)
def watch(symbol: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    person_id = _person(user)
    i = instrument(symbol)
    if i is None:
        raise _not_listed(symbol)
    exists = db.scalar(select(WatchItem).where(WatchItem.person_id == person_id, WatchItem.symbol == i.symbol))
    if exists is None:
        db.add(WatchItem(person_id=person_id, symbol=i.symbol))
        db.commit()
    return Response(status_code=204)


@router.delete("/me/watchlist/{symbol}", status_code=204)
def unwatch(symbol: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    person_id = _person(user)
    row = db.scalar(select(WatchItem).where(WatchItem.person_id == person_id,
                                            WatchItem.symbol == symbol.strip().upper()))
    if row is not None:
        db.delete(row)
        db.commit()
    return Response(status_code=204)
