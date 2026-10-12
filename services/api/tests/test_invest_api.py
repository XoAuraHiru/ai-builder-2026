import json

from sqlalchemy import select

from app.ai.llm import FakeLLM, get_llm
from app.models import AIDecision
from app.seed.funds import seed_funds

HDR = {"X-Dev-User": "priya@atrium.demo"}
BODY = {"initial_usd": 10000, "monthly_usd": 500, "years": 10, "goal_usd": 120000,
        "scenarios": [{"allocation": {"ATR-BAL": 1}},
                      {"label": "Growth tilt", "allocation": {"ATR-GRW": 0.7, "ATR-INC": 0.3}}]}


def facts_of(prompt):
    return json.loads(prompt.split("<facts>")[-1].split("</facts>")[0])


def test_what_if_simulates_real_history(client, db, people):
    seed_funds(db)
    db.commit()
    r = client.post("/invest/what-if", json=BODY, headers=HDR)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["window_start"].startswith("2007") and out["paths"] == 10000
    assert [s["label"] for s in out["scenarios"]] == ["Atrium Balanced", "Growth tilt"]
    first = out["scenarios"][0]
    assert len(first["yearly"]) == 11 and first["yearly"][-1]["contributed"] == 70000
    assert first["final"]["p10"] < first["final"]["p50"] < first["final"]["p90"]
    assert 0 <= first["prob_goal"] <= 100 and first["fee_cost"] > 0
    assert "not a forecast" in out["method"]


def test_what_if_rejects_bad_input(client, db, people):
    seed_funds(db)
    db.commit()
    assert client.post("/invest/what-if", json={**BODY, "initial_usd": 0, "monthly_usd": 0}, headers=HDR).status_code == 422
    assert client.post("/invest/what-if", json={**BODY, "years": 41}, headers=HDR).status_code == 422
    bad_fund = {**BODY, "scenarios": [{"allocation": {"NOPE": 1}}]}
    assert client.post("/invest/what-if", json=bad_fund, headers=HDR).status_code == 422
    assert client.post("/invest/what-if", json=BODY).status_code == 401


def test_explanation_figures_are_checked_against_the_engine(client, db, people):
    seed_funds(db)
    db.commit()

    def honest(prompt):
        s = facts_of(prompt)["scenarios"][0]
        return {"headline": f"Your middle outcome is ${s['median_outcome_usd']:,}.",
                "paragraphs": [f"There is a {s['chance_of_goal_pct']}% chance of reaching your goal."], "cautions": []}

    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({"whatif_narrative": honest})
    body = client.post("/invest/what-if/explain", json=BODY, headers=HDR).json()
    assert body["narrative"]["verified"] is True and body["narrative"]["unsupported_figures"] == []
    assert body["result"]["scenarios"][0]["final"]["p50"] > 0
    assert db.scalars(select(AIDecision.purpose)).all() == ["whatif_narrative"]

    invented = {"headline": "You will have $9,999,999.", "paragraphs": ["Expect 433% a year."], "cautions": []}
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({"whatif_narrative": invented})
    narrative = client.post("/invest/what-if/explain", json=BODY, headers=HDR).json()["narrative"]
    assert narrative["verified"] is False and narrative["unsupported_figures"] == ["$9,999,999", "433%"]


def test_explanation_failure_is_503_with_the_figures_still_valid(client, db, people):
    seed_funds(db)
    db.commit()
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({})
    r = client.post("/invest/what-if/explain", json=BODY, headers=HDR)
    assert r.status_code == 503 and "figures above are complete" in r.json()["detail"]
