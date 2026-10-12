from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Fund, Price
from app.schemas.funds import FundOut, PriceOut

router = APIRouter(prefix="/funds", tags=["funds"])


def _fund_or_404(db: Session, code: str) -> Fund:
    fund = db.scalar(select(Fund).where(Fund.code == code))
    if fund is None:
        raise HTTPException(status_code=404, detail=f"fund {code} not found")
    return fund


@router.get("", response_model=list[FundOut])
def list_funds(db: Session = Depends(get_db)):
    return db.scalars(select(Fund).order_by(Fund.risk_band, Fund.code)).all()


@router.get("/{code}", response_model=FundOut)
def get_fund(code: str, db: Session = Depends(get_db)):
    return _fund_or_404(db, code)


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
