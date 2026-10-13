import pytest
from sqlalchemy import select

from app.ai.llm import FakeLLM, get_llm
from app.config import get_settings
from app.models import AIDecision, Analysis
from app.seed.funds import seed_funds

HDR = {"X-Dev-User": "priya@atrium.demo"}
TRUST = {"kind": "unit_trust", "code": "ATR-BAL", "initial_usd": 10000, "monthly_usd": 200, "years": 10,
         "device_id": "device-visitor-1"}
SHARE = {"kind": "share", "code": "nvda", "initial_usd": 5000, "years": 10, "device_id": "device-visitor-1"}


@pytest.fixture()
def funds(db):
    seed_funds(db)
    db.commit()


def test_visitor_can_analyse_a_unit_trust_without_signing_in(client, db, funds):
    r = client.post("/analyzer", json=TRUST)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["name"] == "Atrium Balanced" and out["comparison"] is None
    assert out["result"]["window_start"].startswith("2007") and out["result"]["contributed"] == 10000 + 200 * 120
    s = out["result"]["scenarios"][0]
    assert s["final"]["p10"] < s["final"]["p50"] < s["final"]["p90"] and s["fee_cost"] > 0
    assert "0.35% annual fee" in out["result"]["method"]
    row = db.get(Analysis, out["id"])
    assert row.person_id is None and row.device_id == "device-visitor-1" and row.ip_hash
    assert row.summary["median_usd"] == s["final"]["p50"]


def test_share_analysis_is_compared_with_the_sp500(client, db, funds):
    out = client.post("/analyzer", json=SHARE).json()
    assert out["code"] == "NVDA" and out["fee_bps"] == 0
    assert out["comparison"]["label"] == "S&P 500 (SPY)"
    assert len(out["result"]["scenarios"]) == 1
    assert "S&P 500 is simulated on the same months" in out["result"]["method"]


def test_signed_in_analysis_records_the_person(client, db, funds, people):
    out = client.post("/analyzer", json=TRUST, headers=HDR).json()
    assert db.get(Analysis, out["id"]).person_id == people["investor"].id


def test_bad_credentials_are_refused_not_treated_as_a_visitor(client, db, funds):
    assert client.post("/analyzer", json=TRUST, headers={"X-Dev-User": "nobody@x.test"}).status_code == 401


@pytest.mark.parametrize("patch, message", [
    ({"initial_usd": 0}, "one-time amount"),
    ({"initial_usd": 100}, "Atrium Balanced needs at least $500"),
    ({"monthly_usd": 20}, "Monthly amounts start at $50"),
    ({"years": 41}, "1 to 40 years"),
    ({"code": "NOPE"}, "Choose one of Atrium's funds"),
])
def test_unit_trust_rules_answer_in_words(client, db, funds, patch, message):
    r = client.post("/analyzer", json={**TRUST, **patch})
    assert r.status_code == 422 and message in r.json()["detail"]


def test_share_rules_answer_in_words(client, db, funds):
    r = client.post("/analyzer", json={**SHARE, "monthly_usd": 100})
    assert r.status_code == 422 and "unit trusts only" in r.json()["detail"]
    r = client.post("/analyzer", json={**SHARE, "code": "SGOV"})
    assert r.status_code == 422 and "too little history" in r.json()["detail"]


def test_refused_runs_are_not_saved(client, db, funds):
    client.post("/analyzer", json={**TRUST, "initial_usd": 0})
    assert db.scalars(select(Analysis)).all() == []


def test_per_device_limit(client, db, funds, monkeypatch):
    monkeypatch.setattr(get_settings(), "analyzer_limit_per_hour", 2)
    assert [client.post("/analyzer", json=TRUST).status_code for _ in range(3)] == [201, 201, 429]
    # a different device on the same network is the same caller
    assert client.post("/analyzer", json={**TRUST, "device_id": "device-visitor-2"}).status_code == 429


def test_global_limit(client, db, funds, monkeypatch):
    monkeypatch.setattr(get_settings(), "analyzer_global_per_hour", 1)
    assert client.post("/analyzer", json=TRUST).status_code == 201
    r = client.post("/analyzer", json=TRUST)
    assert r.status_code == 429 and "busy" in r.json()["detail"]


def test_options_list_funds_and_shares(client, db, funds):
    out = client.get("/analyzer/options").json()
    assert [f["risk_band"] for f in out["funds"]] == sorted(f["risk_band"] for f in out["funds"])
    assert {"ATR-BAL", "ATR-TEC"} <= {f["code"] for f in out["funds"]}
    symbols = {s["symbol"] for s in out["shares"]}
    assert {"NVDA", "SPY"} <= symbols and "SGOV" not in symbols
    assert out["min_share_years"] == 10 and out["monthly_minimum"] == 50


def test_explain_needs_sign_in(client, db, funds):
    analysis = client.post("/analyzer", json=TRUST).json()
    assert client.post(f"/analyzer/{analysis['id']}/explain").status_code == 401


def test_explain_writes_a_checked_narrative(client, db, funds, people):
    analysis = client.post("/analyzer", json=SHARE).json()
    median = round(analysis["result"]["scenarios"][0]["final"]["p50"])
    reply = {"headline": f"A median of ${median:,} and a made-up $1,234,567.",
             "paragraphs": ["One company's past is no guide to its future."]}
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({"analyzer_narrative": reply})
    r = client.post(f"/analyzer/{analysis['id']}/explain", headers=HDR)
    assert r.status_code == 200, r.text
    narrative = r.json()["narrative"]
    assert narrative["unsupported_figures"] == ["$1,234,567"] and not narrative["verified"]
    decision = db.scalars(select(AIDecision).where(AIDecision.purpose == "analyzer_narrative")).one()
    assert decision.subject_id == analysis["id"]


def test_explain_says_busy_when_gemini_fails(client, db, funds, people):
    analysis = client.post("/analyzer", json=TRUST).json()
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({})
    r = client.post(f"/analyzer/{analysis['id']}/explain", headers=HDR)
    assert r.status_code == 503


def test_someone_elses_analysis_cannot_be_explained(client, db, funds, people):
    analysis = client.post("/analyzer", json=TRUST, headers={"X-Dev-User": "daniel@atrium.demo"}).json()
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({"analyzer_narrative": {"headline": "x",
                                                                                       "paragraphs": ["y"]}})
    assert client.post(f"/analyzer/{analysis['id']}/explain", headers=HDR).status_code == 404
