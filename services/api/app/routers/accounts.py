from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account
from app.schemas.portfolio import PortfolioOut
from app.services.portfolio import PriceUnavailable, valuation

router = APIRouter(prefix="/accounts", tags=["accounts"])


def account_or_404(db: Session, account_id: str) -> Account:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail=f"account {account_id} not found")
    return acc


@router.get("/{account_id}/portfolio", response_model=PortfolioOut)
def get_portfolio(account_id: str, as_of: date | None = Query(None), db: Session = Depends(get_db)):
    account_or_404(db, account_id)
    try:
        return valuation(db, account_id, as_of or date.today())
    except PriceUnavailable as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
