"""Scenario Studio: replay 2008, 2020 and 2022 on what an account holds, or map a scenario written in plain English
into bounded shocks (Gemini, grounded with Google Search) that the investor can change and apply."""
from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.llm import LLM, LLMError, get_llm
from app.auth import CurrentUser, get_current_user
from app.db import get_db
from app.governance.breakers import BreakerOpen
from app.models import Account
from app.routers.accounts import account_or_404
from app.routers.insights import NO_HOLDINGS, holdings_of
from app.routers.invest import EXPLAIN_BUSY
from app.services.analytics import universe
from app.services.narrative import NarrativeOut
from app.services.portfolio import PortfolioView
from app.services.scenarios import (NOTHING_TO_TEST, apply_shocks, bound_shocks, explain_impact, is_empty,
                                    map_scenario, replays)

router = APIRouter(prefix="/accounts", tags=["scenarios"])
MAPPING_UNAVAILABLE = "Scenario mapping is unavailable right now."


class MapIn(BaseModel):
    text: str = Field(min_length=3, max_length=400)


class ShocksIn(BaseModel):
    shocks: dict[str, float] = Field(default_factory=dict, max_length=32)


def portfolio_of(db: Session, account_id: str, user: CurrentUser) -> tuple[Account, PortfolioView]:
    """The account and its valuation, access-checked by holdings_of. An account worth nothing is an empty view here,
    not an error: the page says there is nothing to stress-test."""
    try:
        return holdings_of(db, account_id, user)
    except HTTPException as e:
        if e.status_code == 409 and e.detail == NO_HOLDINGS:
            return account_or_404(db, account_id), PortfolioView(account_id=account_id, as_of=date.today())
        raise


def invested(db: Session, account_id: str, user: CurrentUser) -> tuple[Account, PortfolioView]:
    account, view = portfolio_of(db, account_id, user)
    if is_empty(view):
        raise HTTPException(status_code=422, detail=NOTHING_TO_TEST)
    return account, view


def bounded(body: ShocksIn) -> dict[str, float]:
    shocks, _kept, _clamped, _dropped = bound_shocks(list(body.shocks.items()))
    return shocks


@router.get("/{account_id}/scenarios/history")
def history(account_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    _, view = portfolio_of(db, account_id, user)
    if is_empty(view):
        return {"replays": [], "empty": True}
    return {"replays": [asdict(r) for r in replays(view, universe(db))], "empty": False}


@router.post("/{account_id}/scenarios/map")
def map_text(account_id: str, body: MapIn, db: Session = Depends(get_db), llm: LLM = Depends(get_llm),
             user: CurrentUser = Depends(get_current_user)):
    account, view = invested(db, account_id, user)
    try:
        out = map_scenario(db, llm, account, view, body.text)
    except BreakerOpen as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except LLMError as e:
        db.commit()  # keep the grounded call's record: it was made and paid for
        raise HTTPException(status_code=503, detail=MAPPING_UNAVAILABLE) from e
    db.commit()
    impact = out["impact"]
    return {**out, "proposal": out["proposal"].model_dump(), "impact": asdict(impact) if impact else None}


@router.post("/{account_id}/scenarios/apply")
def apply(account_id: str, body: ShocksIn, db: Session = Depends(get_db),
          user: CurrentUser = Depends(get_current_user)):
    _, view = invested(db, account_id, user)
    return asdict(apply_shocks(view, universe(db), bounded(body)))


@router.post("/{account_id}/scenarios/explain", response_model=NarrativeOut)
def explain(account_id: str, body: ShocksIn, db: Session = Depends(get_db), llm: LLM = Depends(get_llm),
            user: CurrentUser = Depends(get_current_user)):
    account, view = invested(db, account_id, user)
    try:
        narrative = explain_impact(db, llm, account, view, bounded(body))
    except LLMError as e:
        raise HTTPException(status_code=503, detail=EXPLAIN_BUSY) from e
    db.commit()
    return narrative
