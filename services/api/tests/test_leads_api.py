import pytest

from app.config import get_settings
from app.events import InProcessEventBus, set_event_bus

STAFF = {"X-Dev-User": "daniel@atrium.demo"}
INVESTOR = {"X-Dev-User": "priya@atrium.demo"}
LEAD = {"source": "web", "full_name": "Ava Thompson", "email": "ava@example.test", "phone": "+14155550123",
        "country": "US", "goals": "Grow savings for retirement in 20 years", "horizon_years": 20,
        "investable_usd": "60000", "monthly_usd": "500", "source_of_funds": "salary",
        "device_id": "dev-ava-0001"}


def test_create_lead_is_public_and_returns_ack_without_scores(client, people):
    r = client.post("/leads", json=LEAD)
    assert r.status_code == 201
    assert set(r.json()) == {"id", "status"} and r.json()["status"] == "received"


@pytest.mark.parametrize("field,value", [("email", "not-an-email"), ("investable_usd", "-5"),
                                         ("country", "us"), ("device_id", "x"), ("horizon_years", 99)])
def test_create_lead_validates_input(client, people, field, value):
    assert client.post("/leads", json={**LEAD, field: value}).status_code == 422


def test_capture_guard_limits_submissions_per_device(client, people, monkeypatch):
    monkeypatch.setattr(get_settings(), "lead_capture_limit_per_hour", 3)
    for i in range(3):
        assert client.post("/leads", json={**LEAD, "email": f"a{i}@example.test"}).status_code == 201
    r = client.post("/leads", json={**LEAD, "email": "a9@example.test"})
    assert r.status_code == 429 and "try again" in r.json()["detail"]


def test_lead_endpoints_are_staff_only(client, people):
    lead_id = client.post("/leads", json=LEAD).json()["id"]
    assert client.get("/leads").status_code == 401
    assert client.get("/leads", headers=INVESTOR).status_code == 403
    assert client.get(f"/leads/{lead_id}", headers=INVESTOR).status_code == 403
    listed = client.get("/leads", headers=STAFF).json()
    assert [x["id"] for x in listed] == [lead_id] and listed[0]["stage"] == "new"


def test_change_stage(client, people):
    lead_id = client.post("/leads", json=LEAD).json()["id"]
    r = client.patch(f"/leads/{lead_id}/stage", json={"stage": "qualified"}, headers=STAFF)
    assert r.status_code == 200 and r.json()["stage"] == "qualified"
    assert client.patch(f"/leads/{lead_id}/stage", json={"stage": "client"}, headers=STAFF).status_code == 422
    assert client.patch(f"/leads/{lead_id}/stage", json={"stage": "bogus"}, headers=STAFF).status_code == 422
    assert client.patch("/leads/nope/stage", json={"stage": "qualified"}, headers=STAFF).status_code == 404
    assert client.get("/leads?stage=qualified", headers=STAFF).json()[0]["id"] == lead_id


def test_lead_created_event(client, people):
    bus = InProcessEventBus()
    set_event_bus(bus)
    lead_id = client.post("/leads", json=LEAD).json()["id"]
    assert any(e.type == "LeadCreated" and e.payload["lead_id"] == lead_id for e in bus.history)


def _analysis(client, db, device="device-visitor-1"):
    from app.seed.funds import seed_funds

    if not client.get("/analyzer/options").json()["funds"]:
        seed_funds(db)
        db.commit()
    return client.post("/analyzer", json={"kind": "unit_trust", "code": "ATR-BAL", "initial_usd": 20000,
                                          "monthly_usd": 300, "years": 15, "device_id": device}).json()


def test_lead_keeps_its_analysis_and_staff_see_it(client, db, people):
    analysis = _analysis(client, db)
    lead_id = client.post("/leads", json={**LEAD, "analysis_id": analysis["id"]}).json()["id"]
    shown = client.get(f"/leads/{lead_id}", headers=STAFF).json()["analysis"]
    assert shown["id"] == analysis["id"] and shown["name"] == "Atrium Balanced" and shown["years"] == 15
    assert shown["summary"]["median_usd"] == analysis["result"]["scenarios"][0]["final"]["p50"]


def test_unknown_used_or_stale_analysis_is_dropped_not_fatal(client, db, people):
    from datetime import timedelta

    from app.models import Analysis, Lead
    from app.models.base import utcnow

    r = client.post("/leads", json={**LEAD, "analysis_id": "does-not-exist"})
    assert r.status_code == 201 and db.get(Lead, r.json()["id"]).analysis_id is None

    analysis = _analysis(client, db)
    first = client.post("/leads", json={**LEAD, "analysis_id": analysis["id"]}).json()["id"]
    second = client.post("/leads", json={**LEAD, "email": "b@example.test", "analysis_id": analysis["id"]}).json()["id"]
    assert db.get(Lead, first).analysis_id == analysis["id"] and db.get(Lead, second).analysis_id is None

    stale = _analysis(client, db)
    db.get(Analysis, stale["id"]).created_at = utcnow() - timedelta(days=8)
    db.commit()
    third = client.post("/leads", json={**LEAD, "email": "c@example.test", "analysis_id": stale["id"]}).json()["id"]
    assert db.get(Lead, third).analysis_id is None


def test_lead_without_analysis_shows_none(client, people):
    lead_id = client.post("/leads", json=LEAD).json()["id"]
    assert client.get(f"/leads/{lead_id}", headers=STAFF).json()["analysis"] is None
