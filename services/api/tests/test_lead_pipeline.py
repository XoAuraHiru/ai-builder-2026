from app.ai.llm import FakeLLM, get_llm
from app.seed.funds import seed_funds
from app.services.lead_pipeline import score_pending

STAFF = {"X-Dev-User": "daniel@atrium.demo"}
LEAD = {"source": "web", "full_name": "Ava Thompson", "email": "ava@example.test", "phone": "+14155550123",
        "country": "US", "goals": "Grow savings for retirement in 20 years", "horizon_years": 20,
        "investable_usd": "60000", "monthly_usd": "500", "source_of_funds": "salary", "device_id": "dev-ava-0001"}
ENRICHED = {"goal_category": "growth", "goals_summary": "Retirement growth.", "suggested_funds": ["ATR-GRW"],
            "stated_risk_appetite": "medium", "consistency_issues": [], "text_authenticity": "natural",
            "next_best_action": "Book a goals call.", "confidence": 0.8}


def use_llm(client, llm):
    client.app.dependency_overrides[get_llm] = lambda: llm
    return llm


def test_capture_scores_lead_immediately(client, db, people):
    seed_funds(db)
    use_llm(client, FakeLLM({"lead_enrichment": ENRICHED}))
    lead_id = client.post("/leads", json=LEAD).json()["id"]
    lead = client.get(f"/leads/{lead_id}", headers=STAFF).json()
    assert 0 <= lead["lead_score"] <= 100 and lead["trust_band"] == "clear"
    assert lead["next_best_action"] == "Book a goals call." and lead["scoring_error"] is None
    decisions = client.get(f"/leads/{lead_id}/decisions", headers=STAFF).json()
    assert [d["purpose"] for d in decisions] == ["lead_enrichment"]


def test_capture_survives_llm_failure(client, db, people):
    seed_funds(db)
    use_llm(client, FakeLLM({}))  # every call raises LLMError
    r = client.post("/leads", json=LEAD)
    assert r.status_code == 201
    lead = client.get(f"/leads/{r.json()['id']}", headers=STAFF).json()
    assert lead["lead_score"] is not None and lead["trust_band"] == "clear"
    assert "unavailable" in lead["scoring_error"]


def test_score_pending_scores_only_unscored(db, make_lead):
    seed_funds(db)
    a, b = make_lead(), make_lead(email="b@example.test", phone=None)
    llm = FakeLLM({"lead_enrichment": ENRICHED})
    assert score_pending(db, llm) == 2 and a.scored_at and b.scored_at
    assert score_pending(db, llm) == 0 and len(llm.calls) == 2


def test_rescore_picks_up_a_later_duplicate(client, db, people):
    seed_funds(db)
    use_llm(client, FakeLLM({"lead_enrichment": ENRICHED}))
    first = client.post("/leads", json=LEAD).json()["id"]
    client.post("/leads", json={**LEAD, "email": "twin@example.test", "device_id": "dev-twin-0001"})
    assert client.get(f"/leads/{first}", headers=STAFF).json()["trust_band"] == "clear"
    rescored = client.post(f"/leads/{first}/rescore", headers=STAFF).json()
    assert any(s["code"] == "T04" for s in rescored["trust_signals"])


def test_ai_usage_totals(client, db, people):
    seed_funds(db)
    use_llm(client, FakeLLM({"lead_enrichment": ENRICHED}))
    client.post("/leads", json=LEAD)
    usage = client.get("/ai/usage", headers=STAFF).json()
    assert usage["decisions"] == 1 and usage["by_purpose"]["lead_enrichment"]["count"] == 1
    assert client.get("/ai/usage", headers={"X-Dev-User": "priya@atrium.demo"}).status_code == 403


def test_score_pending_works_in_small_batches_and_reports_what_remains(client, db, people, make_lead):
    seed_funds(db)
    use_llm(client, FakeLLM({"lead_enrichment": ENRICHED}))
    for i in range(12):
        make_lead(email=f"batch{i}@example.test", phone=None, device_id=f"dev-batch-{i:04d}")
    first = client.post("/leads/score-pending", headers=STAFF).json()
    assert first == {"scored": 10, "remaining": 2}
    assert client.post("/leads/score-pending", headers=STAFF).json() == {"scored": 2, "remaining": 0}
