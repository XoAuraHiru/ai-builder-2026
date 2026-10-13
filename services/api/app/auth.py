"""Who is calling, and what may they see.

dev mode:      header `X-Dev-User: <email>` names a seeded person (local runs and the demo persona picker).
firebase mode: header `Authorization: Bearer <Firebase ID token>`; the token's uid or email maps to a Person.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Account, Person

STAFF_KINDS = {"advisor", "ops", "compliance", "admin"}


@dataclass(frozen=True)
class CurrentUser:
    uid: str
    email: str
    roles: list[str]
    person_id: str | None

    @property
    def is_staff(self) -> bool:
        return "staff" in self.roles


def _roles_for(person: Person) -> list[str]:
    return [person.kind, "staff"] if person.kind in STAFF_KINDS else [person.kind]


def _verify_firebase_token(token: str) -> dict:
    import firebase_admin
    from firebase_admin import auth as fb_auth

    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    return fb_auth.verify_id_token(token)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    if get_settings().auth_mode == "dev":
        email = (request.headers.get("X-Dev-User") or "").strip().lower()
        if not email:
            raise _unauthorized("X-Dev-User header required in dev auth mode")
        person = db.scalar(select(Person).where(Person.email == email))
        if person is None:
            raise _unauthorized(f"no person with email {email}")
        return CurrentUser(uid=f"dev:{email}", email=email, roles=_roles_for(person), person_id=person.id)

    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        raise _unauthorized("Bearer token required")
    try:
        claims = _verify_firebase_token(header.split(" ", 1)[1].strip())
    except Exception as e:  # firebase raises several exception types; all mean "not authenticated"
        raise _unauthorized("invalid or expired token") from e
    uid, email = claims.get("uid", ""), (claims.get("email") or "").lower()
    person = db.scalar(select(Person).where(Person.firebase_uid == uid))
    # Email is only proof of identity once Firebase has verified it; self sign-up can claim any address.
    if person is None and email and claims.get("email_verified") is True:
        person = db.scalar(select(Person).where(Person.email == email))
        if person is not None and not person.firebase_uid:
            person.firebase_uid = uid
            db.commit()
    if person is None:
        raise _unauthorized("authenticated user is not registered")
    return CurrentUser(uid=uid, email=email, roles=_roles_for(person), person_id=person.id)


def optional_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser | None:
    """For public endpoints: no credentials means a visitor (None). Credentials that are sent must still be valid."""
    if not (request.headers.get("X-Dev-User") or request.headers.get("Authorization")):
        return None
    return get_current_user(request, db)


def require_roles(*roles: str):
    def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not set(roles) & set(user.roles):
            raise HTTPException(status_code=403, detail=f"requires one of roles {sorted(roles)}")
        return user

    return _dep


def assert_account_access(user: CurrentUser, account: Account) -> None:
    if user.is_staff or account.person_id == user.person_id:
        return
    raise HTTPException(status_code=403, detail="not your account")
