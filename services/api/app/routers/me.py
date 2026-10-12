from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.db import get_db
from app.models import Account, Person

router = APIRouter(tags=["me"])


class AccountRef(BaseModel):
    id: str
    number: str


class MeOut(BaseModel):
    uid: str
    email: str
    full_name: str | None
    roles: list[str]
    person_id: str | None
    accounts: list[AccountRef]


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MeOut:
    accounts: list[AccountRef] = []
    full_name: str | None = None
    if user.person_id:
        person = db.get(Person, user.person_id)
        full_name = person.full_name if person else None
        rows = db.scalars(select(Account).where(Account.person_id == user.person_id).order_by(Account.number)).all()
        accounts = [AccountRef(id=a.id, number=a.number) for a in rows]
    return MeOut(uid=user.uid, email=user.email, full_name=full_name, roles=user.roles, person_id=user.person_id,
                 accounts=accounts)
