from datetime import date

import pytest

from app.config import get_settings
from app.seed.generate import generate


@pytest.fixture()
def world(db):
    generate(db, get_settings(), end=date(2026, 10, 9))
    db.commit()


def test_me_returns_roles_and_accounts(client, world):
    r = client.get("/me", headers={"X-Dev-User": "priya@atrium.demo"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "priya@atrium.demo" and body["roles"] == ["investor"]
    assert body["full_name"] == "Priya Raman"
    assert len(body["accounts"]) == 1 and body["accounts"][0]["number"] == "ACC-0001"
    staff = client.get("/me", headers={"X-Dev-User": "daniel@atrium.demo"}).json()
    assert staff["roles"] == ["advisor", "staff"] and staff["accounts"] == []
    assert staff["full_name"] == "Daniel Okafor"


def test_me_requires_auth(client, world):
    assert client.get("/me").status_code == 401


def test_cors_allows_configured_origin(client, world):
    r = client.options("/funds", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
