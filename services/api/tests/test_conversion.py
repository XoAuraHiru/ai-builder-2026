from app.events import InProcessEventBus, set_event_bus

STAFF = {"X-Dev-User": "daniel@atrium.demo"}


def qualify(client, lead_id):
    client.patch(f"/leads/{lead_id}/stage", json={"stage": "qualified"}, headers=STAFF)


def test_convert_creates_investor_and_account_who_can_sign_in(client, db, people, make_lead):
    bus = InProcessEventBus()
    set_event_bus(bus)
    lead = make_lead(enrichment={"stated_risk_appetite": "high"}, trust_band="clear", trust_score=100)
    qualify(client, lead.id)
    r = client.post(f"/leads/{lead.id}/convert", json={}, headers=STAFF)
    assert r.status_code == 201, r.text
    assert r.json()["account_number"].startswith("ACC-")
    me = client.get("/me", headers={"X-Dev-User": "ava@example.test"}).json()
    assert me["roles"] == ["investor"] and me["accounts"][0]["id"] == r.json()["account_id"]
    assert client.get(f"/leads/{lead.id}", headers=STAFF).json()["stage"] == "client"
    assert any(e.type == "ClientOnboarded" for e in bus.history)


def test_convert_requires_a_qualified_lead(client, people, make_lead):
    lead = make_lead()
    assert client.post(f"/leads/{lead.id}/convert", json={}, headers=STAFF).status_code == 409


def test_high_risk_needs_a_documented_override(client, people, make_lead):
    lead = make_lead(trust_band="high_risk", trust_score=40)
    qualify(client, lead.id)
    r = client.post(f"/leads/{lead.id}/convert", json={}, headers=STAFF)
    assert r.status_code == 409 and "override" in r.json()["detail"]
    ok = client.post(f"/leads/{lead.id}/convert", json={"override_reason": "Verified by video call on 12 Oct"},
                     headers=STAFF)
    assert ok.status_code == 201


def test_existing_email_and_double_conversion_are_refused(client, people, make_lead):
    taken = make_lead(email="priya@atrium.demo", trust_band="clear")
    qualify(client, taken.id)
    assert client.post(f"/leads/{taken.id}/convert", json={}, headers=STAFF).status_code == 409
    lead = make_lead(email="new@example.test", trust_band="clear")
    qualify(client, lead.id)
    assert client.post(f"/leads/{lead.id}/convert", json={}, headers=STAFF).status_code == 201
    again = client.post(f"/leads/{lead.id}/convert", json={}, headers=STAFF)
    assert again.status_code == 409 and "already" in again.json()["detail"]
