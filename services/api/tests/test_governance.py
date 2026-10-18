"""The Model Risk Office foundation: the inventory, the breakers, the evaluation framework and its runner."""
from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from sqlalchemy import select

from app.governance import inventory
from app.governance.inventory import KINDS, MODELS, TIERS, missing_sources, version, versions
from app.governance.breakers import BreakerError, BreakerOpen, breaker_message, breaker_open, ensure_closed, reset, trip
from app.models import AIDecision, ModelBreaker, Person
from app.events import current_bus, emit
from app.governance.evals import framework
from app.governance.evals.framework import (CaseResult, SuiteResult, every_case, rate, run_case, scratch_db,
                                            share_passing, suite)
from app.governance.evals.runner import (COOLDOWN, RUN_TIMEOUT, adopt_or_start, finish_failed, run_blocker, run_evals,
                                         run_state, start_run, store_run)
from app.models import EvalCase, EvalRun

PERSONA_EMAILS = {f"{p}@atrium.demo" for p in ("daniel", "priya", "lucas", "tom", "hana", "mei", "sam", "omar")}
NOT_YET_BUILT: set[str] = set()  # every model's module exists now


def test_the_inventory_lists_every_model_once_with_what_governs_it():
    assert len(MODELS) == 18
    for key, spec in MODELS.items():
        assert spec.key == key and spec.kind in KINDS and spec.tier in TIERS, key
        assert spec.owner in PERSONA_EMAILS and spec.purpose and spec.human_gate and spec.limitations, key
        assert spec.sources, key
    high_with_fallback = {k for k, s in MODELS.items() if s.tier == "high" and s.fallback}
    assert {"reconciler_agent", "case_reviewer", "call_analyst", "draft_compliance"} <= high_with_fallback


def test_every_built_model_resolves_its_sources():
    for key, spec in MODELS.items():
        if key not in NOT_YET_BUILT:
            assert missing_sources(spec) == [], key


def test_a_version_is_stable_and_changes_when_its_text_changes(monkeypatch):
    spec = MODELS["case_reviewer"]
    first = version(spec)
    assert len(first) == 10 and version(spec) == first and versions()["case_reviewer"] == first
    real = inventory._source_text
    monkeypatch.setattr(inventory, "_source_text", lambda s: real(s) + " changed")
    assert version(spec) != first


NOW = datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)


@pytest.fixture()
def omar(db):
    person = Person(kind="compliance", full_name="Omar Haddad", email="omar@atrium.demo", totp_secret="MFRGGZDFMZTWQ2LK")
    db.add(person)
    db.commit()
    return person


def test_a_breaker_is_closed_until_tripped_and_says_why_when_open(db):
    assert breaker_open(db, "case_reviewer") is False and breaker_message(db, "case_reviewer") is None
    ensure_closed(db, "case_reviewer")
    trip(db, "case_reviewer", reason="It missed its bar in the live checks.", by="Live checks", now=NOW)
    db.flush()
    assert breaker_open(db, "case_reviewer") is True
    assert breaker_message(db, "case_reviewer") == "Case review is paused: It missed its bar in the live checks. Since Oct 14."
    with pytest.raises(BreakerOpen) as raised:
        ensure_closed(db, "case_reviewer")
    assert raised.value.key == "case_reviewer" and "paused" in str(raised.value)
    trip(db, "case_reviewer", reason="A second reason.", by="Omar Haddad", now=NOW)
    assert db.get(ModelBreaker, "case_reviewer").reason == "It missed its bar in the live checks."  # the first stays


def test_resetting_needs_a_reason_and_the_current_code(db, omar):
    trip(db, "reconciler_agent", reason="Kill switch for the demo.", by="Omar Haddad", now=NOW)
    with pytest.raises(BreakerError, match="code"):
        reset(db, "reconciler_agent", reason="Fixed.", person=omar, code="000000", now=NOW)
    with pytest.raises(BreakerError, match="reason"):
        reset(db, "reconciler_agent", reason="  ", person=omar, code=pyotp.TOTP(omar.totp_secret).at(NOW), now=NOW)
    row = reset(db, "reconciler_agent", reason="The prompt was fixed and revalidated.", person=omar,
                code=pyotp.TOTP(omar.totp_secret).at(NOW), now=NOW)
    assert row.state == "closed" and [h["state"] for h in row.history] == ["open", "closed"]
    assert breaker_open(db, "reconciler_agent") is False
    purposes = set(db.scalars(select(AIDecision.purpose)).all())
    assert {"breaker_open", "breaker_reset"} <= purposes
    with pytest.raises(BreakerError, match="not paused"):
        reset(db, "reconciler_agent", reason="Again.", person=omar, code=pyotp.TOTP(omar.totp_secret).at(NOW), now=NOW)
    with pytest.raises(BreakerError, match="no model"):
        trip(db, "made_up", reason="x", by="y", now=NOW)


def test_an_unreadable_breaker_counts_as_open(db, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(db, "get", broken)
    assert breaker_open(db, "case_reviewer") is True
    assert "cannot be checked" in breaker_message(db, "case_reviewer")


def test_a_tripped_breaker_tells_compliance_and_the_models_owner_once(db, omar, people, inbox):
    reason = "It missed its bar in the live checks (accuracy 71%; the bar is 80%)."
    trip(db, "lead_enrichment", reason=reason, by="Live checks", now=NOW)
    db.commit()
    for person in (omar, people["advisor"]):  # compliance, and Daniel, who owns the model
        [told] = inbox.to(person)
        assert (told.id, told.stage, told.severity, told.actor) == (
            "model_paused-lead_enrichment-1", "govern", "attention", "Live checks")
        assert (told.title, told.href) == ("Lead enrichment is paused", "/compliance/models/lead_enrichment")
        assert told.body == f"{reason} Offline rules read the form instead."
    trip(db, "lead_enrichment", reason="Again.", by="Live checks", now=NOW)  # already open: nothing new
    db.commit()
    assert len(inbox.sent) == 2 and inbox.to(people["investor"]) == []




@pytest.fixture()
def registry():
    """Suites registered by a test never outlive it. The real suites load first, so restoring keeps them."""
    framework.load_suites()
    saved = list(framework.SUITES)
    yield
    framework.SUITES[:] = saved


def test_a_scratch_database_is_separate_from_the_live_one(db):
    with scratch_db() as scratch:
        scratch.add(Person(kind="investor", full_name="Scratch Only", email="scratch@example.test"))
        scratch.commit()
        assert scratch.scalar(select(Person.full_name)) == "Scratch Only"
    assert db.scalar(select(Person.full_name)) is None


def test_an_unreachable_model_is_an_error_not_a_fail():
    from app.ai.llm import LLMError

    def check():
        raise LLMError("quota")

    result = run_case("c1", check)
    assert result.outcome == "error" and "could not be reached" in result.detail
    assert share_passing([result]) is None
    assert share_passing([result, CaseResult("c2", "pass"), CaseResult("c3", "fail")]) == 0.5
    judged = rate("case_reviewer", "golden", "live", [result], bar="b", metric="m", value=None, threshold=0.8)
    assert judged.passed is False and judged.metric.startswith("No result")
    assert every_case("lead_score", "golden", "free", [CaseResult("a", "pass")], bar="b").passed is True
    assert every_case("lead_score", "golden", "free", [], bar="b").passed is False


def test_a_run_trips_only_high_risk_models_with_a_fallback_that_missed_their_bar(db, registry):
    keys = {"case_reviewer", "lead_enrichment", "reconciler_agent", "narration_reader"}
    framework.SUITES[:] = [s for s in framework.SUITES if s.model_key not in keys]  # only this test's suites for these

    @suite("case_reviewer", tier="live")
    def failing_high(ctx):
        emit("SomethingInsideACase", {"x": 1})  # must not reach the live event stream
        return SuiteResult("case_reviewer", "golden", "live", "bar", "2 of 5", False,
                           [CaseResult("a", "fail"), CaseResult("b", "pass")])

    @suite("lead_enrichment", tier="live")
    def failing_medium(ctx):
        return SuiteResult("lead_enrichment", "golden", "live", "bar", "1 of 2", False, [CaseResult("a", "fail")])

    @suite("reconciler_agent", tier="live")
    def all_errors(ctx):
        return SuiteResult("reconciler_agent", "golden", "live", "bar", "No result", False, [CaseResult("a", "error")])

    @suite("narration_reader", tier="live")
    def crashes(ctx):
        raise RuntimeError("boom")

    outer = current_bus()
    report = run_evals("live", only={"case_reviewer", "lead_enrichment", "reconciler_agent", "narration_reader"})
    assert "SomethingInsideACase" not in [e.type for e in outer.history]
    crashed = next(s for s in report.suites if s.model_key == "narration_reader")
    assert crashed.passed is False and crashed.cases[0].outcome == "error" and "boom" in crashed.cases[0].detail
    run = start_run(db, tier="live", trigger="deploy", now=NOW)
    tripped = store_run(db, report, run, now=NOW)
    assert tripped == ["case_reviewer"]
    assert breaker_open(db, "case_reviewer") and not breaker_open(db, "lead_enrichment")
    assert not breaker_open(db, "reconciler_agent")  # every case errored: nothing was learned
    assert run.status == "finished" and run.summary["counts"] == {"suites": 4, "passed": 0}
    assert db.scalar(select(EvalCase.case_id).where(EvalCase.model_key == "case_reviewer", EvalCase.outcome == "fail")) == "a"
    assert run.models["case_reviewer"] == versions()["case_reviewer"]


def test_free_suites_also_run_in_a_live_run_but_live_suites_never_run_free(registry):
    calls = []

    @suite("lead_score", kind="fairness")
    def free_one(ctx):
        calls.append(("free", ctx.llm))
        return SuiteResult("lead_score", "fairness", "free", "b", "m", True, [CaseResult("a", "pass")])

    @suite("lead_enrichment", tier="live")
    def live_one(ctx):
        calls.append(("live", ctx.llm))
        return SuiteResult("lead_enrichment", "golden", "live", "b", "m", True, [CaseResult("a", "pass")])

    run_evals("free", only={"lead_score", "lead_enrichment"}, llm="LLM")
    assert ("live", "LLM") not in calls and ("free", None) in calls
    calls.clear()
    run_evals("live", only={"lead_score", "lead_enrichment"}, llm="LLM")
    assert ("free", None) in calls and ("live", "LLM") in calls


def test_the_button_waits_for_a_running_run_and_for_the_cooldown(db):
    assert run_blocker(db, now=NOW) is None
    run = start_run(db, tier="live", trigger="deploy", now=NOW)
    db.flush()
    assert "still going" in run_blocker(db, now=NOW + timedelta(minutes=3))
    assert run_state(run, now=NOW + RUN_TIMEOUT + timedelta(minutes=1)) == "did_not_finish"
    assert run_blocker(db, now=NOW + RUN_TIMEOUT + timedelta(minutes=1)) is None
    finish_failed(db, run, RuntimeError("x"), now=NOW + timedelta(minutes=2))
    assert run.status == "failed" and run_blocker(db, now=NOW + timedelta(minutes=5)) is None
    done = start_run(db, tier="live", trigger="deploy", now=NOW + timedelta(hours=1))
    done.status, done.finished_at = "finished", NOW + timedelta(hours=1, minutes=5)
    db.flush()
    assert "next can start" in run_blocker(db, now=NOW + timedelta(hours=1, minutes=20))
    assert run_blocker(db, now=NOW + timedelta(hours=1, minutes=5) + COOLDOWN) is None


def test_the_job_adopts_the_run_the_button_asked_for(db):
    asked = start_run(db, tier="live", trigger="button", requested_by="Omar Haddad", now=NOW)
    db.flush()
    assert adopt_or_start(db, tier="live", trigger="deploy", now=NOW + timedelta(minutes=2)).id == asked.id
    other = adopt_or_start(db, tier="live", trigger="deploy", now=NOW + timedelta(minutes=30))
    assert other.id != asked.id and other.trigger == "deploy"


def test_a_live_suite_judges_only_the_cases_that_reached_the_model():
    live = every_case("call_analyst", "golden", "live", [CaseResult("a", "pass"), CaseResult("b", "error")], bar="b")
    assert live.passed is True and live.metric == "1 of 1 cases passed (1 could not reach the model)"
    none = every_case("call_analyst", "golden", "live", [CaseResult("a", "error"), CaseResult("b", "error")], bar="b")
    assert none.passed is False and none.metric.startswith("No result")
    free = every_case("lead_score", "golden", "free", [CaseResult("a", "pass"), CaseResult("b", "error")], bar="b")
    assert free.passed is False  # the free tier has no model to blame: an error there is a failure


def test_a_small_sample_bar_counts_misses_instead_of_rounding_a_percentage_up_to_all():
    from app.governance.evals.framework import within_misses

    cases = [CaseResult(str(i), "pass") for i in range(5)]
    assert within_misses("lead_enrichment", "fairness", "live", cases, bar="b", metric="17 of 18",
                         judged=18, misses=1, max_misses=1).passed is True
    assert within_misses("lead_enrichment", "fairness", "live", cases, bar="b", metric="16 of 18",
                         judged=18, misses=2, max_misses=1).passed is False
    nothing = within_misses("lead_enrichment", "fairness", "live", cases, bar="b", metric="m",
                            judged=0, misses=0, max_misses=1)
    assert nothing.passed is False and nothing.metric.startswith("No result")


def test_the_runner_waits_exactly_as_long_as_the_job_may_run():
    import re
    from pathlib import Path as P

    deploy = (P(__file__).resolve().parents[3] / "infra" / "deploy.sh").read_text(encoding="utf-8")
    job = deploy[deploy.index("run jobs deploy atrium-evals"):]
    seconds = int(re.search(r"--task-timeout (\d+)", job).group(1))
    assert RUN_TIMEOUT.total_seconds() == seconds == 75 * 60

