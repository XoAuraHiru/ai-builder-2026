import re

from sqlalchemy import select

from app.ai.llm import FakeLLM, get_llm
from app.models import AIDecision, Proposal
from app.seed.funds import house_fund_objects, seed_funds
from app.services.proposal import provisional_band, recommend_mix

STAFF = {"X-Dev-User": "daniel@atrium.demo"}
FUNDS = house_fund_objects()


def test_provisional_band_is_capped_by_the_horizon(db, make_lead):
    lead = make_lead(horizon_years=20)
    lead.enrichment = {"stated_risk_appetite": "high"}
    assert provisional_band(lead)[0] == 4
    lead.horizon_years = 2
    assert provisional_band(lead)[0] == 2


def test_recommendation_keeps_only_suitable_suggested_funds():
    assert recommend_mix(FUNDS, 4, ["ATR-TEC", "ATR-GRW"]) == {"ATR-GRW": 1.0}
    assert recommend_mix(FUNDS, 3, ["ATR-BAL", "ATR-DIV"]) == {"ATR-BAL": 0.6, "ATR-DIV": 0.4}
    assert recommend_mix(FUNDS, 2, []) == {"ATR-INC": 1.0}


def proposal_llm(extra=""):
    def write(prompt):
        ids = re.findall(r'<passage id="([^"]+)"', prompt)
        firm = [i for i in ids if i.startswith("ATRIUM#")][:1]
        return {"sections": [
            {"key": "why_atrium", "heading": "Why Atrium", "body": "Every recommendation is explained.", "citations": firm},
            {"key": "recommendation", "heading": "Our suggestion", "body": "A balanced mix." + extra,
             "citations": [ids[0], "ATR-ZZZ#nope"]},
            {"key": "projection", "heading": "What it could become", "body": "See the simulation.",
             "citations": ["projection"]},
            {"key": "fees", "heading": "Fees", "body": "One yearly fee.", "citations": []},
            {"key": "risks", "heading": "Risks", "body": "You can lose money.", "citations": [ids[1]]}]}
    return FakeLLM({"proposal": write, "compliance_review": {"findings": []}})


def test_proposal_is_grounded_checked_and_stored(client, db, people, make_lead):
    seed_funds(db)
    lead = make_lead()
    lead.enrichment = {"stated_risk_appetite": "medium", "suggested_funds": ["ATR-BAL"]}
    db.commit()
    client.app.dependency_overrides[get_llm] = lambda: proposal_llm(" It could reach $9,999,999.")
    r = client.post(f"/leads/{lead.id}/proposal", headers=STAFF)
    assert r.status_code == 201, r.text
    body = r.json()
    sections = {s["key"]: s for s in body["content"]["sections"]}
    assert "ATR-ZZZ#nope" not in sections["recommendation"]["citations"]
    assert sections["fees"]["grounded"] is False and sections["projection"]["citations"] == ["projection"]
    assert body["unsupported_figures"] == ["$9,999,999"] and body["verified"] is False
    assert body["allocation"] == {"ATR-BAL": 1.0} and body["compliance"]["ok"] is True and body["band"] == 3
    scenarios = body["content"]["projection"]["scenarios"]
    assert [s["label"] for s in scenarios] == ["Recommended mix", "Cash reserve only"] and scenarios[0]["yearly"]
    assert [p["id"] for p in client.get(f"/leads/{lead.id}/proposals", headers=STAFF).json()] == [body["id"]]
    assert {"proposal", "compliance_review"} <= set(db.scalars(select(AIDecision.purpose)).all())


def test_risky_leads_get_no_proposal_and_investors_cannot_ask(client, db, people, make_lead):
    seed_funds(db)
    lead = make_lead()
    lead.trust_band = "high_risk"
    db.commit()
    client.app.dependency_overrides[get_llm] = lambda: proposal_llm()
    r = client.post(f"/leads/{lead.id}/proposal", headers=STAFF)
    assert r.status_code == 409 and "trust review" in r.json()["detail"]
    assert client.post(f"/leads/{lead.id}/proposal", headers={"X-Dev-User": "priya@atrium.demo"}).status_code == 403


def test_writer_failure_is_503_and_stores_nothing(client, db, people, make_lead):
    seed_funds(db)
    lead = make_lead()
    db.commit()
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({})
    assert client.post(f"/leads/{lead.id}/proposal", headers=STAFF).status_code == 503
    assert db.scalars(select(Proposal)).all() == []
