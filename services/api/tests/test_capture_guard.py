from app.config import get_settings

LEAD = {"source": "web", "full_name": "Ava Thompson", "email": "ava@example.test", "phone": "+14155550123",
        "country": "US", "goals": "Grow savings for retirement in 20 years", "horizon_years": 20,
        "investable_usd": "60000", "monthly_usd": "500", "source_of_funds": "salary"}


def test_spoofed_forwarded_for_does_not_reset_the_per_ip_limit(client, people, monkeypatch):
    """Cloud Run appends the address it saw; whatever the client put first is attacker-controlled."""
    monkeypatch.setattr(get_settings(), "lead_capture_limit_per_hour", 2)
    for i in range(2):
        headers = {"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"}
        body = {**LEAD, "email": f"a{i}@example.test", "device_id": f"dev-spoof-{i:04d}"}
        assert client.post("/leads", json=body, headers=headers).status_code == 201
    r = client.post("/leads", json={**LEAD, "email": "a9@example.test", "device_id": "dev-spoof-9999"},
                    headers={"X-Forwarded-For": "10.9.9.9, 203.0.113.7"})
    assert r.status_code == 429


def test_global_hourly_cap_bounds_spend_whatever_the_identifiers(client, people, monkeypatch):
    monkeypatch.setattr(get_settings(), "lead_capture_global_per_hour", 3)
    for i in range(3):
        body = {**LEAD, "email": f"g{i}@example.test", "device_id": f"dev-global-{i:04d}"}
        assert client.post("/leads", json=body, headers={"X-Forwarded-For": f"198.51.100.{i}"}).status_code == 201
    r = client.post("/leads", json={**LEAD, "email": "g9@example.test", "device_id": "dev-global-9999"},
                    headers={"X-Forwarded-For": "198.51.100.99"})
    assert r.status_code == 429 and "many applications" in r.json()["detail"]


def test_phone_is_normalised_to_international_form(client, people):
    for typed, stored in [("+1 415 555 0123", "+14155550123"), ("(415) 555-0124", "+14155550124"),
                          ("1-415-555-0125", "+14155550125"), ("555-1234", "5551234")]:
        body = {**LEAD, "email": f"p{stored[-4:]}@example.test", "phone": typed, "device_id": f"dev-ph-{stored[-4:]}"}
        lead_id = client.post("/leads", json=body).json()["id"]
        r = client.get(f"/leads/{lead_id}", headers={"X-Dev-User": "daniel@atrium.demo"})
        assert r.json()["phone"] == stored, typed
