from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.config import get_settings
from app.db import get_db
from app.models import Account, Person
from app.services.approvals import current_code

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


class AuthenticatorOut(BaseModel):
    code: str
    seconds_left: int
    period: int = 30
    note: str


@router.get("/me/authenticator", response_model=AuthenticatorOut)
def authenticator(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> AuthenticatorOut:
    """The demo authenticator. With persona sign-in, staff have no phone app enrolled, so the workspace shows the code
    their authenticator would show. With real sign-in this does not exist: codes come from the person's own app."""
    if get_settings().auth_mode != "dev":
        raise HTTPException(status_code=404, detail="Not Found")
    if not user.is_staff:
        raise HTTPException(status_code=403, detail="Only Atrium staff have an authenticator.")
    person = db.get(Person, user.person_id)
    enrolled = bool(person.totp_secret)
    code, seconds_left = current_code(person)
    if not enrolled:
        db.commit()  # the secret current_code just created
    return AuthenticatorOut(code=code, seconds_left=seconds_left,
                            note="Demo authenticator: in production this code comes from the staff member's own app.")
