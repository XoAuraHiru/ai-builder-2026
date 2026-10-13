"""Fair lending and production monitoring."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.ai.llm import FakeLLM
from app.governance import golden
from app.governance.breakers import breaker_open
from app.governance.evals.framework import EvalContext
from app.governance.evals.suites import lead_enrichment, lead_score
from app.governance.fairness import COUNTRIES, NAME_VARIANTS, variants
from app.governance.monitoring import MIN_DECISIONS, agreement, apply_monitoring_breakers, drift, monitoring
from app.models import Account, AmlAlert, Lead, Person, ReconMatch, TradeOrder

NOW = datetime(2026, 10, 14, 15, tzinfo=timezone.utc)


def test_the_score_does_not_move_when_only_the_name_or_country_changes():
    assert len(NAME_VARIANTS) == 6 and len(COUNTRIES) == 3
    assert len(variants({"full_name": "x", "country": "US"}, NAME_VARIANTS, COUNTRIES)) == 18
    result = lead_score.fair_lending(EvalContext(tier="free"))
    assert result.kind == "fairness" and result.passed and len(result.cases) == 12
    assert all(c["why"] and c["fields"] for c in golden.load("fairness/leads")["cases"])


def test_a_score_that_reads_the_name_fails_fair_lending(monkeypatch):
    real = lead_score.score_lead
    monkeypatch.setattr(lead_score, "score_lead",
                        lambda lead, enrichment: (real(lead, enrichment)[0] + ("Aisha" in lead.full_name), {}))
    result = lead_score.fair_lending(EvalContext(tier="free"))
    assert result.passed is False and all(c.outcome == "fail" for c in result.cases)


def test_live_fair_lending_compares_names_side_by_side():
    leads = golden.load("fairness/leads")["cases"]
    answer = golden.load("lead_enrichment/leads")["cases"][0]["answer"]
    same = lead_enrichment.fair_lending_live(EvalContext(tier="live", llm=FakeLLM({"lead_enrichment": answer})))
    assert same.kind == "fairness" and same.passed and len(same.cases) == 6
    assert len(leads) == 12

    def biased(prompt):
        return {**answer, "goal_category": "income"} if "DeShawn" in prompt else answer

    differ = lead_enrichment.fair_lending_live(EvalContext(tier="live", llm=FakeLLM({"lead_enrichment": biased})))
    assert differ.passed is False
    assert any("DeShawn Washington" in str(c.actual) for c in differ.cases if c.outcome == "fail")


def _match(db, proposed_by, state, when):
    db.add(ReconMatch(line_ids=["l"], instruction_ids=["i"], tier="fuzzy", confidence=0.7, evidence=["e"],
                      proposed_by=proposed_by, state=state, decided_by="x", decided_at=when))


def test_too_few_decisions_are_not_a_rate_and_do_not_trip(db):
    for _ in range(MIN_DECISIONS - 1):
        _match(db, "agent", "rejected", NOW - timedelta(days=1))
    db.flush()
    recon = agreement(db, now=NOW)["reconciler_agent"]
    assert recon["rate"] is None and "not enough" in recon["note"].lower()
    assert apply_monitoring_breakers(db, now=NOW) == [] and not breaker_open(db, "reconciler_agent")


def test_people_rejecting_most_agent_proposals_trips_the_agent(db):
    for i in range(12):
        _match(db, "agent", "rejected" if i < 8 else "accepted", NOW - timedelta(days=2))
    _match(db, "agent", "rejected", NOW - timedelta(days=40))  # outside the window
    _match(db, "scorer", "accepted", NOW - timedelta(days=3))
    _match(db, "mei@atrium.demo", "accepted", NOW - timedelta(days=3))  # a manual match is nobody's model
    db.flush()
    found = agreement(db, now=NOW)
    recon = found["reconciler_agent"]
    assert recon["decided"] == 12 and round(recon["rate"], 2) == 0.33
    assert recon["by"]["scorer"]["decided"] == 1 and recon["by"]["rules"]["decided"] == 0
    assert apply_monitoring_breakers(db, now=NOW) == ["reconciler_agent"] and breaker_open(db, "reconciler_agent")
    assert "33% of 12 decisions" in db.get(__import__("app.models", fromlist=["ModelBreaker"]).ModelBreaker,
                                           "reconciler_agent").reason
    assert "agreement" in monitoring(db, now=NOW) and monitoring(db, now=NOW)["window_days"] == 30


def test_the_stored_evals_run_applies_the_monitoring_breakers(db, monkeypatch):
    import app.governance.monitoring as monitoring_module
    from app.governance.evals.__main__ import main

    calls = []
    monkeypatch.setattr(monitoring_module, "apply_monitoring_breakers", lambda session, now=None: calls.append(1) or [])
    monkeypatch.setattr("app.governance.evals.__main__.run_evals",
                        lambda tier, **kw: __import__("app.governance.evals.runner", fromlist=["x"]).RunReport(
                            tier, [], {}, NOW, NOW))
    assert main(["--tier", "free", "--store"]) == 0 and calls == [1]


def test_a_day_end_with_people_rejecting_the_agent_trips_it(db, monkeypatch):
    from app.ai.offline import offline_llm
    from app.ops.day_end import run_day_end

    for i in range(12):
        _match(db, "agent", "rejected", datetime.now(timezone.utc) - timedelta(days=1))
    db.flush()
    run = run_day_end(db, now=datetime.now(timezone.utc), triggered_by="test", llm=offline_llm())
    step = next(s for s in run.steps if s["step"] == "Model monitoring")
    assert step["facts"] == {"tripped": ["reconciler_agent"]} and "Reconciliation agent" in step["detail"]
    assert breaker_open(db, "reconciler_agent")


def _person_account(db, n):
    person = Person(kind="investor", full_name=f"Client {n}", email=f"client{n}@example.test")
    db.add(person)
    db.flush()
    account = Account(person_id=person.id, number=f"ACC-9{n:03d}", opened_on=date(2025, 1, 2))
    db.add(account)
    db.flush()
    return person, account


def test_case_review_agreement_counts_escalate_and_close_and_skips_requests(db):
    person, account = _person_account(db, 1)
    for k, (state, triage) in enumerate([("escalated", "escalate")] * 6 + [("closed", "close")] * 4
                                        + [("closed", "escalate")] * 2 + [("escalated", "request_information")] * 3):
        db.add(AmlAlert(scenario="structuring", title="t", severity="high", score=0.9, person_id=person.id,
                        account_id=account.id, summary="s", evidence=[], fingerprint=f"{k:064d}", state=state,
                        ai_review={"triage": triage}, decided_by=person.id, decided_at=NOW - timedelta(days=1)))
    db.flush()
    review = agreement(db, now=NOW)["case_reviewer"]
    assert review["decided"] == 12 and review["agreed"] == 10 and round(review["rate"], 2) == 0.83


def test_held_order_agreement_reads_the_advisor_decision(db):
    _, account = _person_account(db, 2)
    pairs = [("released", "release")] * 7 + [("rejected", "reject")] * 2 + [("released", "reject")] * 2 \
        + [("rejected", "call_client")]
    for k, (decision, suggestion) in enumerate(pairs):
        db.add(TradeOrder(account_id=account.id, symbol="KO", side="buy", order_type="market", quantity=1,
                          state="filled" if decision == "released" else "rejected", verdict="hold", guardian={},
                          estimated_value=Decimal("60"), broker="atrium-paper", trust_score=100, trust_band="clear",
                          timeline=[{"state": "held", "note": "", "at": ""}, {"state": decision, "note": "", "at": ""}],
                          reviewed_at=NOW - timedelta(days=1), ai_review={"suggestion": suggestion}))
    db.flush()
    held = agreement(db, now=NOW)["held_order_reviewer"]
    assert held["decided"] == 11 and held["agreed"] == 9


def test_drift_needs_twenty_recent_leads_and_measures_psi(db):
    def lead(n, score):
        row = Lead(source="web", full_name=f"Lead {n}", email=f"lead{n}@example.test", country="US", goals="g",
                   horizon_years=10, investable_usd=Decimal("1000"), monthly_usd=Decimal("0"), device_id=f"d{n}",
                   lead_score=score, scored_at=NOW - timedelta(days=1))
        db.add(row)

    for n in range(5):
        lead(n, 50)
    db.flush()
    few = drift(db, now=NOW)["lead_score"]
    assert few["psi"] is None and "20" in few["note"]
    for n in range(5, 40):
        lead(n, 99)
    db.flush()
    shifted = drift(db, now=NOW)["lead_score"]
    assert shifted["psi"] > 0.25 and shifted["warn"] is True and shifted["recent"] == 40
    assert "aml_anomaly" in drift(db, now=NOW)
