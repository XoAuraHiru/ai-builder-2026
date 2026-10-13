from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm import LLM, LLMError, get_llm
from app.auth import CurrentUser, get_current_user
from app.db import get_db
from app.knowledge.docs import cached_facts, fund_doc
from app.knowledge.fit import fund_fit
from app.knowledge.search import get_fund_search
from app.models import Fund, Person, Price
from app.schemas.funds import FundOut, PriceOut, UnitHistoryOut
from app.schemas.knowledge import FitOut, FundExplainerOut, FundStatsOut, SectionOut
from app.services.unit_history import unit_history

router = APIRouter(prefix="/funds", tags=["funds"])
FIT_BUSY = "The AI reading is unavailable right now; the fund facts on this page are complete. Try again in a minute."


def _fund_or_404(db: Session, code: str) -> Fund:
    fund = db.scalar(select(Fund).where(Fund.code == code))
    if fund is None:
        raise HTTPException(status_code=404, detail=f"fund {code} not found")
    return fund


@router.get("", response_model=list[FundOut])
def list_funds(db: Session = Depends(get_db)):
    return db.scalars(select(Fund).order_by(Fund.risk_band, Fund.code)).all()


@router.get("/stats", response_model=list[FundStatsOut])
def fund_stats(db: Session = Depends(get_db)):
    out = []
    for fund in db.scalars(select(Fund).order_by(Fund.risk_band, Fund.code)).all():
        f = cached_facts(fund.code)
        out.append(FundStatsOut(code=fund.code, name=fund.name, risk_band=fund.risk_band,
                                annual_return_pct=f["annual_return_pct"], annual_volatility_pct=f["annual_volatility_pct"],
                                max_drawdown_pct=f["max_drawdown_pct"], best_year=f["best_year"],
                                worst_year=f["worst_year"], total_fee_pct=f["fees"]["total_pct"],
                                window_start=f["window_start"], window_end=f["window_end"]))
    return out


@router.get("/{code}", response_model=FundOut)
def get_fund(code: str, db: Session = Depends(get_db)):
    return _fund_or_404(db, code)


@router.get("/{code}/explainer", response_model=FundExplainerOut)
def explainer(code: str, db: Session = Depends(get_db)):
    fund = _fund_or_404(db, code)
    facts = cached_facts(code)
    sections = [SectionOut(id=s.id, title=s.title, paragraphs=s.paragraphs,
                           table=None if s.table is None else {"head": s.table[0], "rows": s.table[1]})
                for s in fund_doc(fund, facts).sections]
    return FundExplainerOut(fund=FundOut.model_validate(fund), facts=facts, sections=sections)


@router.post("/{code}/fit", response_model=FitOut)
def fit(code: str, db: Session = Depends(get_db), llm: LLM = Depends(get_llm), search=Depends(get_fund_search),
        user: CurrentUser = Depends(get_current_user)):
    fund = _fund_or_404(db, code)
    person = db.get(Person, user.person_id) if user.person_id else None
    if person is None or person.kind != "investor":
        raise HTTPException(status_code=403, detail="Fund readings are for investors.")
    try:
        out = fund_fit(db, llm, search, fund, person)
    except LLMError as e:
        raise HTTPException(status_code=503, detail=FIT_BUSY) from e
    db.commit()
    return out


@router.get("/{code}/prices", response_model=list[PriceOut])
def fund_prices(
    code: str,
    start: date | None = Query(None),
    end: date | None = Query(None),
    db: Session = Depends(get_db),
):
    _fund_or_404(db, code)
    q = select(Price).where(Price.fund_code == code, Price.status == "published")
    if start:
        q = q.where(Price.as_of >= start)
    if end:
        q = q.where(Price.as_of <= end)
    return db.scalars(q.order_by(Price.as_of)).all()


@router.get("/{code}/unit-history", response_model=UnitHistoryOut)
def fund_unit_history(code: str, db: Session = Depends(get_db)):
    """Public: the unit price since 2007, published from launch and a flagged backtest before it."""
    fund = _fund_or_404(db, code)
    published = db.execute(select(Price.as_of, Price.nav).where(Price.fund_code == code, Price.status == "published")
                           .order_by(Price.as_of)).all()
    return UnitHistoryOut(code=fund.code, name=fund.name, inception_on=fund.inception_on,
                          points=unit_history(fund, [(d, nav) for d, nav in published]))
