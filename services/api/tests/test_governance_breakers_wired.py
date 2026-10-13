"""An open breaker takes each feature to its fallback, and the page is told why."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.ai.llm import FakeLLM, get_llm
from app.governance import golden
from app.governance.breakers import trip

NOW = datetime(2026, 10, 14, 15, tzinfo=timezone.utc)
OMAR = {"X-Dev-User": "omar@atrium.demo"}
DANIEL = {"X-Dev-User": "daniel@atrium.demo"}


@pytest.fixture()
def alert(db, staff):
    from app.models import Account, AmlAlert, Person

    person = Person(kind="investor", full_name="Arjun Mehta", email="arjun@example.test")
    db.add(person)
    db.flush()
    account = Account(person_id=person.id, number="ACC-0001", opened_on=date(2025, 1, 2))
    db.add(account)
    db.flush()
    row = AmlAlert(scenario="structuring", title="Possible structuring", severity="high", score=0.9,
                   person_id=person.id, account_id=account.id, summary="Three payments just under $10,000.00.",
                   evidence=[{"kind": "instruction", "id": "e1", "date": "2026-10-06", "amount": "9400.00",
                              "detail": "Subscription of $9,400.00"}], fingerprint="f" * 64)
    db.add(row)
    db.commit()
    return row


def test_a_paused_case_reviewer_returns_503_with_its_reason(client, db, alert):
    llm = FakeLLM({})
    client.app.dependency_overrides[get_llm] = lambda: llm
    trip(db, "case_reviewer", reason="It missed its bar in the live checks.", by="Live checks", now=NOW)
    db.commit()
    response = client.post(f"/compliance/alerts/{alert.id}/review", headers=OMAR)
    assert response.status_code == 503 and "Case review is paused" in response.json()["detail"]
    assert llm.calls == []
    shown = client.get(f"/compliance/alerts/{alert.id}", headers=OMAR).json()
    assert shown["review_paused"].startswith("Case review is paused: It missed its bar")


def test_an_alert_says_nothing_is_paused_when_the_breaker_is_closed(client, db, alert):
    assert client.get(f"/compliance/alerts/{alert.id}", headers=OMAR).json()["review_paused"] is None


def test_a_paused_reconciler_uses_the_scorer_and_says_so(db):
    from app.agents.reconciler import reconcile
    from app.governance.evals.suites.reconciler_agent import build_scenario

    scenario = next(s for s in golden.load("reconciler_agent/scenarios")["cases"] if s["id"] == "one-character-typo")
    build_scenario(db, scenario)
    trip(db, "reconciler_agent", reason="Kill switch.", by="Omar Haddad", now=NOW)
    result = reconcile(db, model=object(), now=NOW)  # any model: the breaker must stop it being used
    assert "paused" in result["summary"] and result["scorer"] >= 1 and result["used_agent"] is False
    assert "The scorer proposed the strongest matches." in result["summary"]


def test_a_paused_enrichment_reads_the_form_offline(db, make_lead):
    from app.services.enrichment import enrich_lead

    trip(db, "lead_enrichment", reason="Kill switch.", by="Omar Haddad", now=NOW)
    llm = FakeLLM({})  # would raise if called
    enrichment = enrich_lead(db, make_lead(), llm)
    assert llm.calls == [] and enrichment.goal_category


def test_a_paused_draft_check_runs_the_rules_only(db):
    from app.services.compliance import check_compliance

    trip(db, "draft_compliance", reason="Kill switch.", by="Omar Haddad", now=NOW)
    llm = FakeLLM({})
    report = check_compliance("This fund guarantees 8% a year.", llm, db=db, subject_id="lead-1")
    assert llm.calls == [] and report.reviewed_by == ["rules"] and report.findings
    assert report.paused and "Draft compliance check is paused" in report.paused
    told = check_compliance("Fine text.", llm, paused="Draft compliance check is paused: x")
    assert llm.calls == [] and told.reviewed_by == ["rules"]


def test_a_paused_narration_reader_reads_by_rule_and_notes_why(db):
    from app.services.statements import RawLine, normalise

    trip(db, "narration_reader", reason="Kill switch.", by="Omar Haddad", now=NOW)
    llm = FakeLLM({})
    readings, read_by = normalise(db, llm, "statement-1",
                                  [RawLine(date(2026, 10, 12), "ACH CREDIT PRIYA RAMAN REF ATR-1A2B3C4D", Decimal("10"))])
    assert llm.calls == [] and readings[0].reference == "ATR-1A2B3C4D" and readings[0].remitter == "Priya Raman"
    assert read_by.startswith("paused") and "Narration reading is paused" in read_by


def test_a_paused_statement_reader_takes_csv_only(db, staff):
    from app.services.statements import StatementError, ingest_statement

    class Reader:
        def read(self, data, mime_type):  # would be Document AI
            raise AssertionError("the paused reader must not be called")

    trip(db, "statement_reader", reason="Kill switch.", by="Omar Haddad", now=NOW)
    with pytest.raises(StatementError, match="Statement reading is paused"):
        ingest_statement(db, data=b"%PDF-1.4", filename="oct.pdf", mime_type="application/pdf",
                         uploaded_by=staff["mei"], llm=FakeLLM({}), reader=Reader())
    csv = b"Date,Description,Amount\n2026-10-12,ACH CREDIT PRIYA RAMAN REF ATR-1A2B3C4D,1500.00\n"
    statement = ingest_statement(db, data=csv, filename="oct.csv", mime_type="text/csv", uploaded_by=staff["mei"],
                                 llm=FakeLLM({}), reader=Reader())
    assert statement.source == "csv"


def test_a_paused_anomaly_model_leaves_the_scenarios_to_raise_alerts(db, account):
    from app.ml.aml_model import FEATURES, AmlModel
    from app.services.aml import run_monitoring

    flags_everyone = AmlModel(centroids=[[0.0] * 6], means={f: 0.0 for f in FEATURES}, stds={f: 1.0 for f in FEATURES},
                              threshold=-1.0, source="test", model_name="test", trained_at="2026-10-12")
    trip(db, "aml_anomaly", reason="Kill switch.", by="Omar Haddad", now=NOW)
    assert [a.scenario for a in run_monitoring(db, date(2026, 10, 12), flags_everyone)] == []  # scenarios alone ran


def test_a_paused_order_explainer_keeps_the_guardians_report(db, account):
    from app.services.order_ai import explain_order

    trip(db, "pretrade_guardian", reason="Kill switch.", by="Omar Haddad", now=NOW)
    llm = FakeLLM({})
    narrative = explain_order(db, llm, account, {"verdict": "proceed"})
    assert llm.calls == [] and "paused" in narrative.headline.lower() and narrative.model == "paused"


def test_a_paused_review_note_and_proposal_and_copilot_answer_503(client, db, account, people, staff, make_lead):
    from app.agents.runtime import get_agent_model

    llm = FakeLLM({})
    client.app.dependency_overrides[get_llm] = lambda: llm
    for key in ("proposal_writer", "investor_copilot"):
        trip(db, key, reason="Kill switch.", by="Omar Haddad", now=NOW)
    db.commit()
    lead = make_lead()
    proposal = client.post(f"/leads/{lead.id}/proposal", headers=DANIEL)
    assert proposal.status_code == 503 and "Proposal is paused" in proposal.json()["detail"]
    client.app.dependency_overrides[get_agent_model] = lambda: object()
    asked = client.post(f"/accounts/{account.id}/copilot", headers={"X-Dev-User": "priya@example.test"},
                        json={"question": "How am I doing?", "history": []})
    assert asked.status_code == 503 and "Investor Copilot is paused" in asked.json()["detail"]
    assert llm.calls == []


def test_a_paused_held_order_reviewer_answers_503(db):
    from app.governance.breakers import BreakerOpen
    from app.services.order_ai import write_review_note

    trip(db, "held_order_reviewer", reason="Kill switch.", by="Omar Haddad", now=NOW)
    llm = FakeLLM({})
    with pytest.raises(BreakerOpen, match="Held-order review note is paused"):
        write_review_note(db, llm, object())
    assert llm.calls == []


def test_the_review_note_route_turns_a_paused_model_into_503(client, db, account, people, paper):
    from app.markets.broker import PaperBroker, broker_dep
    from app.markets.quotes import CommittedQuotes, quote_book
    from app.models import Person
    import pandas as pd

    paper.deposit(account, "10000")
    db.get(Person, account.person_id).risk_band = 2
    db.commit()
    daily = pd.DataFrame({"TSLA": [400.0, 400.0]}, index=pd.to_datetime(["2026-10-08", "2026-10-09"]))
    client.app.dependency_overrides[quote_book] = lambda: CommittedQuotes(daily)
    client.app.dependency_overrides[broker_dep] = PaperBroker
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({})
    holder = {"X-Dev-User": "priya@example.test", "X-Device-Id": "browser-1"}
    held = client.post(f"/accounts/{account.id}/orders", headers=holder,
                       json={"symbol": "TSLA", "side": "buy", "quantity": 3}).json()
    trip(db, "held_order_reviewer", reason="Kill switch.", by="Omar Haddad", now=NOW)
    db.commit()
    response = client.post(f"/orders/{held['id']}/review-note", headers=DANIEL)
    assert response.status_code == 503 and "Held-order review note is paused" in response.json()["detail"]
