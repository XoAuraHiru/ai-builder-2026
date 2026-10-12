from datetime import date

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import Account, Person
from app.seed.generate import generate

AS_OF = "as_of=2026-10-09"


@pytest.fixture()
def world(db):
    generate(db, get_settings(), end=date(2026, 10, 9))
    db.commit()


def account_of(db, email):
    person = db.scalar(select(Person).where(Person.email == email))
    return db.scalar(select(Account).where(Account.person_id == person.id))


def test_missing_dev_header_is_401(client, world):
    assert client.get("/accounts/anything/portfolio").status_code == 401


def test_malformed_dev_header_is_401_not_500(client, world):
    assert client.get("/accounts/anything/portfolio", headers={"X-Dev-User": "   "}).status_code == 401
    assert client.get("/accounts/anything/portfolio", headers={"X-Dev-User": "nobody@nowhere.test"}).status_code == 401


def test_investor_can_read_own_account_but_not_others(client, db, world):
    own = account_of(db, "priya@atrium.demo")
    other = account_of(db, "lucas@atrium.demo")
    hdr = {"X-Dev-User": "priya@atrium.demo"}
    assert client.get(f"/accounts/{own.id}/portfolio?{AS_OF}", headers=hdr).status_code == 200
    assert client.get(f"/accounts/{other.id}/portfolio?{AS_OF}", headers=hdr).status_code == 403


def test_dev_header_is_case_insensitive(client, db, world):
    own = account_of(db, "priya@atrium.demo")
    r = client.get(f"/accounts/{own.id}/portfolio?{AS_OF}", headers={"X-Dev-User": "Priya@Atrium.Demo"})
    assert r.status_code == 200


def test_staff_can_read_any_account(client, db, world):
    acc = account_of(db, "lucas@atrium.demo")
    for email in ("daniel@atrium.demo", "mei@atrium.demo", "omar@atrium.demo"):
        r = client.get(f"/accounts/{acc.id}/portfolio?{AS_OF}", headers={"X-Dev-User": email})
        assert r.status_code == 200, email


def test_firebase_mode_verifies_bearer_token(client, db, world, monkeypatch):
    import app.auth as auth_mod

    def fake_verify(token):
        if token != "good":
            raise ValueError("bad token")
        return {"uid": "fb-priya", "email": "priya@atrium.demo", "email_verified": True}

    monkeypatch.setattr(get_settings(), "auth_mode", "firebase")
    monkeypatch.setattr(auth_mod, "_verify_firebase_token", fake_verify)
    acc = account_of(db, "priya@atrium.demo")
    url = f"/accounts/{acc.id}/portfolio?{AS_OF}"
    assert client.get(url, headers={"Authorization": "Bearer good"}).status_code == 200
    assert client.get(url, headers={"Authorization": "Bearer bad"}).status_code == 401
    assert client.get(url).status_code == 401
    assert db.scalar(select(Person).where(Person.email == "priya@atrium.demo")).firebase_uid == "fb-priya"


def test_firebase_unverified_email_cannot_claim_a_person(client, db, world, monkeypatch):
    import app.auth as auth_mod

    monkeypatch.setattr(get_settings(), "auth_mode", "firebase")
    monkeypatch.setattr(auth_mod, "_verify_firebase_token",
                        lambda token: {"uid": "attacker", "email": "omar@atrium.demo", "email_verified": False})
    acc = account_of(db, "priya@atrium.demo")
    r = client.get(f"/accounts/{acc.id}/portfolio?{AS_OF}", headers={"Authorization": "Bearer forged"})
    assert r.status_code == 401
    assert db.scalar(select(Person).where(Person.email == "omar@atrium.demo")).firebase_uid is None
