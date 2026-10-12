from app.ai.llm import FakeLLM, get_llm
from app.seed.funds import HOUSE_FUNDS, seed_funds

INVESTOR = {"X-Dev-User": "priya@atrium.demo"}
STAFF = {"X-Dev-User": "daniel@atrium.demo"}


def test_explainer_is_public_and_matches_the_documents(client, db):
    seed_funds(db)
    db.commit()
    body = client.get("/funds/ATR-BAL/explainer").json()
    assert [s["id"] for s in body["sections"]][:4] == ["objective", "what-it-holds", "who-it-suits", "fees"]
    assert body["facts"]["calendar_years"] and body["fund"]["code"] == "ATR-BAL"
    assert body["sections"][1]["table"]["head"][0] == "ETF"
    assert client.get("/funds/NOPE/explainer").status_code == 404


def test_fund_stats_cover_every_fund(client, db):
    seed_funds(db)
    db.commit()
    stats = client.get("/funds/stats").json()
    assert {s["code"] for s in stats} == {spec["code"] for spec in HOUSE_FUNDS}
    assert all(s["total_fee_pct"] > 0 and s["worst_year"]["year"] >= 2007 for s in stats)


def test_fit_flags_a_fund_above_the_profile_and_keeps_only_cited_points(client, db, people):
    seed_funds(db)
    people["investor"].risk_band = 3
    db.commit()
    draft = {"headline": "Atrium Technology is riskier than your profile.",
             "points": [{"text": "It is risk band 5, above your band 3.", "citations": ["ATR-TEC#who-it-suits"]},
                        {"text": "A made-up point.", "citations": ["ATR-TEC#nope"]}],
             "caution": "It can fall far more than the market."}
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({"fund_fit": draft})
    r = client.post("/funds/ATR-TEC/fit", headers=INVESTOR)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["suitability"] == {"fund_band": 5, "your_band": 3, "verdict": "above"}
    assert [p["text"] for p in body["points"]] == ["It is risk band 5, above your band 3."]
    assert [c["id"] for c in body["citations"]] == ["ATR-TEC#who-it-suits"]
    assert body["retriever"] == "local-index" and body["verified"] is True


def test_fit_needs_grounded_points_and_an_investor(client, db, people):
    seed_funds(db)
    db.commit()
    ungrounded = {"headline": "h", "points": [{"text": "x", "citations": ["nope"]}], "caution": "c"}
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({"fund_fit": ungrounded})
    assert client.post("/funds/ATR-BAL/fit", headers=INVESTOR).status_code == 503
    assert client.post("/funds/ATR-BAL/fit", headers=STAFF).status_code == 403
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({})
    assert client.post("/funds/ATR-BAL/fit", headers=INVESTOR).status_code == 503
