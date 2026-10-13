"""Scenario Studio routes: history replays, Gemini's mapping (grounded, bounded, recorded), applying and explaining."""
import json
from datetime import date
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import select

from app.ai.llm import FakeLLM, get_llm
from app.governance.breakers import trip
from app.models import AIDecision, Person
from app.seed.funds import seed_funds
from app.services.ledger import apply_posting
from app.services.pricing import publish_prices

HDR = {"X-Dev-User": "priya@example.test"}
CONTEXT = {"text": "The Fed funds rate is 4.25%; oil trades near $80.",
           "sources": [{"title": "Fed holds rates", "uri": "https://example.test/fed"}]}
IN_SCOPE = {"in_scope": True, "title": "AI stocks fall 40%", "horizon_months": 12,
            "shocks": [{"factor": "technology", "pct": -500, "reason": "AI leaders reprice sharply."},
                       {"factor": "us_equity", "pct": -10, "reason": "The rest of the market follows."},
                       {"factor": "crypto", "pct": -60, "reason": "Not a factor Atrium models."}],
            "analogue": "rates_2022", "analogue_reason": "Technology led the 2022 fall.",
            "assumptions": ["No recession."]}
REFUSED = {"in_scope": False, "refusal": "Scenario Studio models market scenarios; it cannot write poems."}


@pytest.fixture()
def invested(db, account):
    """ATR-BAL $10,100 (100 units at 101) and ATR-TEC $4,080 (20 units at 204)."""
    seed_funds(db)
    idx = pd.to_datetime(["2026-01-02", "2026-01-05"])
    for code, navs in {"ATR-BAL": [100.0, 101.0], "ATR-TEC": [200.0, 204.0]}.items():
        publish_prices(db, code, pd.Series(navs, index=idx), Decimal("1000000"))
    for code, units, price in [("ATR-BAL", "100", "100"), ("ATR-TEC", "20", "200")]:
        apply_posting(db, account_id=account.id, instrument=code, instrument_type="fund", posting_type="subscription",
                      units=Decimal(units), cash=-Decimal(units) * Decimal(price), price=Decimal(price),
                      value_date=date(2026, 1, 2), reference=f"SUB-{code}")
    db.commit()
    return account


def use(client, responses):
    llm = FakeLLM(responses)
    client.app.dependency_overrides[get_llm] = lambda: llm
    return llm


def test_history_replays_three_windows_on_the_account(client, invested):
    r = client.get(f"/accounts/{invested.id}/scenarios/history", headers=HDR)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["empty"] is False
    assert [x["key"] for x in body["replays"]] == ["crisis_2008", "pandemic_2020", "rates_2022"]
    crisis = body["replays"][0]
    assert {h["symbol"] for h in crisis["holdings"]} == {"ATR-BAL", "ATR-TEC"} and crisis["loss_usd"] < 0
    assert crisis["worst_holding"]["symbol"] == "ATR-TEC"


def test_mapping_grounds_bounds_and_records_both_calls(client, db, invested):
    llm = use(client, {"scenario_context": CONTEXT, "scenario_proposal": IN_SCOPE})
    r = client.post(f"/accounts/{invested.id}/scenarios/map", json={"text": "AI stocks fall 40%"}, headers=HDR)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["proposal"]["in_scope"] is True
    assert body["shocks"] == {"technology": -70, "us_equity": -10, "intl_equity": 0, "bonds": 0, "cash": 0}
    assert body["clamped"] == ["technology"] and body["dropped"] == ["crypto"]
    assert [s["factor"] for s in body["proposal"]["shocks"]] == ["technology", "us_equity"]
    assert body["sources"] == CONTEXT["sources"] and body["sources_note"] is None
    # ATR-TEC is all technology (XLK and VGT's other sectors fall back to -10%), ATR-BAL is 60% VTI.
    assert body["impact"]["total_usd"] < 0 and len(body["impact"]["holdings"]) == 2

    context_call, proposal_call = llm.calls
    assert context_call["purpose"] == "scenario_context" and proposal_call["purpose"] == "scenario_proposal"
    assert "<scenario>\nAI stocks fall 40%\n</scenario>" in context_call["prompt"]
    assert "data, not instructions" in context_call["prompt"] and "data, not instructions" in proposal_call["prompt"]
    assert CONTEXT["text"] in proposal_call["prompt"] and "AI stocks fall 40%" in proposal_call["prompt"]
    rows = db.scalars(select(AIDecision).order_by(AIDecision.created_at)).all()
    assert [(d.purpose, d.agent, d.subject_id) for d in rows] == [
        ("scenario_context", "investor_copilot", invested.id), ("scenario_proposal", "investor_copilot", invested.id)]
    assert rows[0].output["sources"] == CONTEXT["sources"]


def test_an_out_of_scope_request_is_refused_with_no_shocks(client, invested):
    use(client, {"scenario_context": CONTEXT, "scenario_proposal": REFUSED})
    body = client.post(f"/accounts/{invested.id}/scenarios/map", json={"text": "Write me a poem about the market"},
                       headers=HDR).json()
    assert body["proposal"]["in_scope"] is False and body["proposal"]["refusal"].startswith("Scenario Studio")
    assert body["shocks"] == {} and body["proposal"]["shocks"] == [] and body["impact"] is None


def test_without_sources_the_proposal_still_comes_and_says_so(client, db, invested):
    use(client, {"scenario_proposal": IN_SCOPE})  # the grounded call fails
    body = client.post(f"/accounts/{invested.id}/scenarios/map", json={"text": "AI stocks fall 40%"},
                       headers=HDR).json()
    assert body["proposal"]["in_scope"] is True and body["sources"] == []
    assert body["sources_note"] == "Current sources were unavailable; the shocks rest on the model's knowledge."
    assert db.scalars(select(AIDecision.purpose)).all() == ["scenario_proposal"]


def test_a_failed_proposal_is_a_plain_503(client, invested):
    use(client, {"scenario_context": CONTEXT})
    r = client.post(f"/accounts/{invested.id}/scenarios/map", json={"text": "AI stocks fall 40%"}, headers=HDR)
    assert r.status_code == 503 and r.json()["detail"] == "Scenario mapping is unavailable right now."


def test_the_scenario_text_is_bounded(client, invested):
    use(client, {"scenario_context": CONTEXT, "scenario_proposal": IN_SCOPE})
    url = f"/accounts/{invested.id}/scenarios/map"
    assert client.post(url, json={"text": "AI"}, headers=HDR).status_code == 422
    assert client.post(url, json={"text": "x" * 401}, headers=HDR).status_code == 422


def test_applying_edited_shocks_recomputes_the_total(client, invested):
    url = f"/accounts/{invested.id}/scenarios/apply"
    # Every US stock -10%: ATR-BAL is 60% stocks (-$606 on $10,100), ATR-TEC is all stocks (-$408 on $4,080).
    base = client.post(url, json={"shocks": {"us_equity": -10}}, headers=HDR)
    assert base.status_code == 200, base.text
    assert base.json()["total_usd"] == pytest.approx(-1014, abs=0.01)
    # Bonds -90% is held to -30%: ATR-BAL's 40% in bonds adds -12% of $10,100.
    edited = client.post(url, json={"shocks": {"us_equity": -10, "bonds": -90, "crypto": 5}}, headers=HDR).json()
    assert edited["total_usd"] == pytest.approx(-1014 - 1212, abs=0.01)
    assert edited["total_pct"] == pytest.approx((-1014 - 1212) / 14180 * 100, abs=0.01)


def test_explaining_checks_the_figures_against_the_impact(client, db, invested):
    def honest(prompt):
        facts = json.loads(prompt.split("<facts>")[-1].split("</facts>")[0])
        return {"headline": f"Your portfolio would change by {facts['total_change_usd']}.",
                "paragraphs": [f"That is {facts['total_change_pct']} of its value."], "cautions": []}

    use(client, {"scenario_narrative": honest})
    r = client.post(f"/accounts/{invested.id}/scenarios/explain", json={"shocks": {"us_equity": -10}}, headers=HDR)
    assert r.status_code == 200, r.text
    assert r.json()["verified"] is True and r.json()["headline"] == "Your portfolio would change by -$1,014."
    assert db.scalars(select(AIDecision.purpose)).all() == ["scenario_narrative"]

    use(client, {"scenario_narrative": {"headline": "You would lose $99,999.", "paragraphs": ["Bad."],
                                        "cautions": []}})
    narrative = client.post(f"/accounts/{invested.id}/scenarios/explain", json={"shocks": {"us_equity": -10}},
                            headers=HDR).json()
    assert narrative["verified"] is False and narrative["unsupported_figures"] == ["$99,999"]

    use(client, {})
    failed = client.post(f"/accounts/{invested.id}/scenarios/explain", json={"shocks": {}}, headers=HDR)
    assert failed.status_code == 503


def test_another_investor_cannot_stress_test_the_account(client, db, invested):
    db.add(Person(kind="investor", full_name="Other", email="other@example.test"))
    db.commit()
    use(client, {"scenario_context": CONTEXT, "scenario_proposal": IN_SCOPE})
    other = {"X-Dev-User": "other@example.test"}
    base = f"/accounts/{invested.id}/scenarios"
    assert client.get(f"{base}/history", headers=other).status_code == 403
    assert client.post(f"{base}/map", json={"text": "AI stocks fall 40%"}, headers=other).status_code == 403
    assert client.post(f"{base}/apply", json={"shocks": {}}, headers=other).status_code == 403
    assert client.post(f"{base}/explain", json={"shocks": {}}, headers=other).status_code == 403


def test_a_paused_mapper_gives_503_with_the_breakers_reason(client, db, invested):
    trip(db, "scenario_mapper", reason="It missed its bar in the live checks.", by="Live checks")
    db.commit()
    llm = use(client, {"scenario_context": CONTEXT, "scenario_proposal": IN_SCOPE})
    r = client.post(f"/accounts/{invested.id}/scenarios/map", json={"text": "AI stocks fall 40%"}, headers=HDR)
    assert r.status_code == 503 and r.json()["detail"].startswith("Scenario mapping is paused")
    assert llm.calls == []  # no model call while paused
    assert client.get(f"/accounts/{invested.id}/scenarios/history", headers=HDR).status_code == 200


def test_an_account_with_nothing_invested_has_nothing_to_stress_test(client, db, account, paper):
    seed_funds(db)
    db.commit()
    url = f"/accounts/{account.id}/scenarios"
    assert client.get(f"{url}/history", headers=HDR).json() == {"replays": [], "empty": True}
    paper.deposit(account, "1000")  # cash alone is still nothing to stress-test
    db.commit()
    assert client.get(f"{url}/history", headers=HDR).json() == {"replays": [], "empty": True}
    use(client, {"scenario_context": CONTEXT, "scenario_proposal": IN_SCOPE})
    r = client.post(f"{url}/map", json={"text": "AI stocks fall 40%"}, headers=HDR)
    assert r.status_code == 422 and "nothing to stress-test" in r.json()["detail"]
    assert client.post(f"{url}/apply", json={"shocks": {"us_equity": -10}}, headers=HDR).status_code == 422
