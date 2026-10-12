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
