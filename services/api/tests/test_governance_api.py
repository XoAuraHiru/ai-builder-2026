"""The Model Risk Office API: the inventory with statuses, each model's card, and its breaker."""
from datetime import datetime, timezone

import pyotp
import pytest

from app.governance.evals.framework import CaseResult, SuiteResult
from app.governance.evals.runner import RunReport, start_run, store_run
from app.governance.inventory import versions

OMAR, MEI = {"X-Dev-User": "omar@atrium.demo"}, {"X-Dev-User": "mei@atrium.demo"}


@pytest.fixture()
def gov(client, staff):
    return client


def test_only_compliance_sees_the_models(gov):
    assert gov.get("/governance/models", headers=MEI).status_code == 403
    body = gov.get("/governance/models", headers=OMAR).json()
    assert len(body["models"]) == 18 and body["last_run"] is None
    by_key = {m["key"]: m for m in body["models"]}
    assert by_key["lead_score"]["status"] == "not_validated"      # has a suite, never run
    assert by_key["held_order_reviewer"]["status"] == "monitored_only"  # no suite at all
    assert by_key["case_reviewer"]["owner"] == "Omar Haddad"  # the owner's name when the person exists


def test_a_stored_run_validates_or_fails_each_model(gov, db):
    report = RunReport("live", [
        SuiteResult("lead_score", "golden", "free", "AUC at least 0.75", "AUC 0.79", True, [CaseResult("auc", "pass")]),
        SuiteResult("aml_scenarios", "golden", "free", "every scenario", "6 of 7", False,
                    [CaseResult("velocity", "fail", detail="did not fire")]),
    ], versions(), datetime(2026, 10, 14, tzinfo=timezone.utc), datetime(2026, 10, 14, tzinfo=timezone.utc))
    run = start_run(db, tier="live", trigger="deploy")
    store_run(db, report, run)
    db.commit()
    by_key = {m["key"]: m for m in gov.get("/governance/models", headers=OMAR).json()["models"]}
    assert by_key["lead_score"]["status"] == "validated" and by_key["lead_score"]["changed_since_validation"] is False
    assert by_key["aml_scenarios"]["status"] == "failing"
    card = gov.get("/governance/models/aml_scenarios", headers=OMAR).json()
    assert card["suites"][0]["cases"][0] == {"case_id": "velocity", "outcome": "fail", "expected": None, "actual": None,
                                             "detail": "did not fire", "cost_usd": "0.000000", "latency_ms": 0}
    assert gov.get("/governance/models/made_up", headers=OMAR).status_code == 404


def test_a_breaker_opens_by_hand_and_resets_with_a_code(gov, staff):
    opened = gov.post("/governance/breakers/case_reviewer/open", headers=OMAR, json={"reason": "Kill switch test."})
    assert opened.status_code == 200 and opened.json()["state"] == "open"
    card = gov.get("/governance/models/case_reviewer", headers=OMAR).json()
    assert card["status"] == "breaker_open" and "paused" in card["breaker"]["message"]
    wrong = gov.post("/governance/breakers/case_reviewer/reset", headers=OMAR, json={"reason": "Fixed.", "code": "000000"})
    assert wrong.status_code == 422 and "code" in wrong.json()["detail"]
    code = pyotp.TOTP(staff["omar"].totp_secret).now()
    done = gov.post("/governance/breakers/case_reviewer/reset", headers=OMAR, json={"reason": "Fixed.", "code": code})
    assert done.status_code == 200 and done.json()["state"] == "closed"
    assert gov.post("/governance/breakers/case_reviewer/open", headers=MEI, json={"reason": "x"}).status_code == 403


def test_pausing_a_model_by_hand_tells_its_owner_but_not_the_person_who_paused_it(gov, staff, people, inbox):
    gov.post("/governance/breakers/lead_enrichment/open", headers=OMAR, json={"reason": "Kill switch test."})
    assert inbox.to(staff["omar"]) == []
    [told] = inbox.to(people["advisor"])  # Daniel owns Lead enrichment
    assert (told.title, told.actor, told.href) == ("Lead enrichment is paused", "Omar Haddad",
                                                   "/compliance/models/lead_enrichment")
