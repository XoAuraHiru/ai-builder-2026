from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.db import get_db
from app.models import Account

router = APIRouter(tags=["me"])


class AccountRef(BaseModel):
    id: str
    number: str


class MeOut(BaseModel):
    uid: str
    email: str
    roles: list[str]
    person_id: str | None
    accounts: list[AccountRef]


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MeOut:
    accounts: list[AccountRef] = []
    if user.person_id:
        rows = db.scalars(select(Account).where(Account.person_id == user.person_id).order_by(Account.number)).all()
        accounts = [AccountRef(id=a.id, number=a.number) for a in rows]
    return MeOut(uid=user.uid, email=user.email, roles=user.roles, person_id=user.person_id, accounts=accounts)
