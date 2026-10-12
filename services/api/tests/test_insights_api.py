from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from app.ai.llm import FakeLLM, get_llm
from app.models import Person
from app.seed.funds import seed_funds
from app.services.ledger import apply_posting
from app.services.pricing import publish_prices

HDR = {"X-Dev-User": "priya@example.test"}


@pytest.fixture()
def invested(db, account):
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


def test_risk_report_for_the_account_holder(client, invested):
    r = client.get(f"/accounts/{invested.id}/risk", headers=HDR)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["months"] >= 200 and body["annual_volatility_pct"] > 0
    assert abs(sum(body["risk_contributions_pct"].values()) - 100) < 0.5
    assert body["portfolio_band"] == 4 and body["verdict"] == "no_profile"


def test_verdict_compares_with_the_profile_band(client, db, invested):
    invested.person.risk_band = 3
    db.commit()
    assert client.get(f"/accounts/{invested.id}/risk", headers=HDR).json()["verdict"] == "above"


def test_xray_for_the_account_holder(client, invested):
    body = client.get(f"/accounts/{invested.id}/xray", headers=HDR).json()
    assert body["total_value_usd"] == 14180.0
    assert body["companies"] and body["companies"][0]["via"]
    assert {e["ticker"] for e in body["etfs"]} == {"VTI", "BND", "XLK", "VGT"}
    assert body["fees"]["total_annual_usd"] > 0 and body["profiles_as_of"]


def test_other_investors_cannot_see_the_analysis(client, db, invested):
    db.add(Person(kind="investor", full_name="Other", email="other@example.test"))
    db.commit()
    other = {"X-Dev-User": "other@example.test"}
    assert client.get(f"/accounts/{invested.id}/risk", headers=other).status_code == 403
    assert client.get(f"/accounts/{invested.id}/xray", headers=other).status_code == 403


def test_an_account_without_holdings_gets_a_clear_409(client, db, account):
    seed_funds(db)
    db.commit()
    r = client.get(f"/accounts/{account.id}/risk", headers=HDR)
    assert r.status_code == 409 and "no holdings" in r.json()["detail"]
    assert client.get(f"/accounts/{account.id}/xray", headers=HDR).status_code == 409


def test_explanations_come_back_with_their_reports(client, invested):
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({
        "risk_narrative": {"headline": "Your portfolio swings more than your profile.",
                           "paragraphs": ["It has moved with the market."], "cautions": []},
        "xray_narrative": {"headline": "You own a lot of technology.",
                           "paragraphs": ["Most of it comes through two ETFs."], "cautions": []}})
    risk = client.post(f"/accounts/{invested.id}/risk/explain", headers=HDR).json()
    assert risk["narrative"]["verified"] is True and risk["report"]["months"] > 0
    xr = client.post(f"/accounts/{invested.id}/xray/explain", headers=HDR).json()
    assert xr["narrative"]["headline"].startswith("You own") and xr["xray"]["total_value_usd"] == 14180.0
