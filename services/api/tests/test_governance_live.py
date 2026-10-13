"""Live suites, graded with FakeLLM: a right answer passes, a wrong one fails, an unreachable model is an error."""
from app.ai.llm import FakeLLM, LLMError
from app.governance import golden
from app.governance.evals.framework import EvalContext
from app.governance.evals.suites import case_reviewer, draft_compliance, lead_enrichment, narration_reader, reconciler_agent


def live(llm, agent_model=None):
    return EvalContext(tier="live", llm=llm, agent_model=agent_model)


def test_every_live_golden_case_says_why_and_carries_a_right_answer():
    for name in ("lead_enrichment/leads", "narration_reader/narrations", "case_reviewer/alerts",
                 "draft_compliance/phrases"):
        cases = golden.load(name)["cases"]
        assert cases and all(c.get("why") and "answer" in c for c in cases), name
    assert len(golden.load("lead_enrichment/leads")["cases"]) == 10
    assert sum(c["expect"]["inconsistent"] for c in golden.load("lead_enrichment/leads")["cases"]) == 4
    assert len(golden.load("narration_reader/narrations")["cases"]) == 12
    assert len(golden.load("case_reviewer/alerts")["cases"]) == 5


def test_enrichment_passes_when_it_reads_the_goals_right_and_fails_when_it_does_not():
    cases = golden.load("lead_enrichment/leads")["cases"]
    right = {c["id"]: c["answer"] for c in cases}  # each golden case carries a correct example answer
    responses = iter([right[c["id"]] for c in cases])
    good = lead_enrichment.golden_leads(live(FakeLLM({"lead_enrichment": lambda prompt: next(responses)})))
    assert good.passed, (good.metric, [(c.case_id, c.actual) for c in good.cases if c.outcome != "pass"])
    wrong = {**cases[0]["answer"], "goal_category": "income"}
    bad = lead_enrichment.golden_leads(live(FakeLLM({"lead_enrichment": wrong})))
    assert bad.passed is False


def test_an_enrichment_that_misses_a_planted_inconsistency_fails_that_lead():
    cases = golden.load("lead_enrichment/leads")["cases"]
    planted = next(c for c in cases if c["expect"]["inconsistent"])
    answers = {c["id"]: c["answer"] for c in cases}
    answers[planted["id"]] = {**planted["answer"], "consistency_issues": []}
    responses = iter([answers[c["id"]] for c in cases])
    result = lead_enrichment.golden_leads(live(FakeLLM({"lead_enrichment": lambda prompt: next(responses)})))
    assert [c.case_id for c in result.cases if c.outcome == "fail"] == [planted["id"]]


def test_narrations_pass_when_read_right():
    cases = golden.load("narration_reader/narrations")["cases"]
    lines = {"lines": [{"line_no": n, **c["answer"]} for n, c in enumerate(cases, start=1)]}
    result = narration_reader.golden_narrations(live(FakeLLM({"statement_normalise": lines})))
    assert result.passed and result.counts["pass"] == 12, [(c.case_id, c.actual) for c in result.cases]


def test_an_unreachable_model_gives_no_result_rather_than_a_fail():
    class Down:
        def generate_json(self, **kwargs):
            raise LLMError("quota exceeded")

    result = narration_reader.golden_narrations(live(Down()))
    assert result.passed is False and result.metric.startswith("No result") and result.counts["error"] == 12


def test_an_empty_review_fails_with_a_reason():
    empty = {"triage": "escalate", "triage_reason": "", "narrative": [{"text": "", "evidence": []}], "questions": []}
    result = case_reviewer.golden_alerts(live(FakeLLM({"aml_case_review": empty})))
    assert result.passed is False and all(c.detail for c in result.cases if c.outcome == "fail")
    assert all("no narrative" in c.detail for c in result.cases)


def test_right_reviews_pass_the_golden_alerts():
    cases = golden.load("case_reviewer/alerts")["cases"]
    answers = iter([c["answer"] for c in cases])
    result = case_reviewer.golden_alerts(live(FakeLLM({"aml_case_review": lambda prompt: next(answers)})))
    assert result.passed and result.counts["pass"] == 5, [(c.case_id, c.detail, c.actual) for c in result.cases]


def test_the_challenger_runs_the_same_alerts_on_flash():
    seen = []

    class Recorder(FakeLLM):
        def generate_json(self, **kwargs):
            seen.append(kwargs.get("pro"))
            return super().generate_json(**kwargs)

    answer = golden.load("case_reviewer/alerts")["cases"][0]["answer"]
    result = case_reviewer.flash_challenger(live(Recorder({"aml_case_review": answer})))
    assert seen and all(p is False for p in seen)
    assert result.kind == "challenger" and "Flash" in result.metric


def test_draft_compliance_live_agrees_with_the_golden_labels():
    phrases = golden.load("draft_compliance/phrases")["cases"]
    answers = iter([p["answer"] for p in phrases])
    result = draft_compliance.gemini_on_phrases(live(FakeLLM({"compliance_review": lambda prompt: next(answers)})))
    assert result.passed, result.metric


def test_draft_compliance_live_that_flags_everything_disagrees():
    flag = {"findings": [{"phrase": "fund", "rule": "promissory", "explanation": "x", "suggestion": "y"}]}
    result = draft_compliance.gemini_on_phrases(live(FakeLLM({"compliance_review": flag})))
    assert result.passed is False


def test_the_agent_suite_without_a_real_agent_records_the_scorer_path_as_no_result():
    from app.agents.runtime import get_agent_model

    result = reconciler_agent.agent_scenarios(live(FakeLLM({}), agent_model=get_agent_model()))
    assert result.passed is False and result.metric.startswith("No result")
    # Two scenarios leave nothing for the agent (the rules settle them); the other eight fell back to the scorer.
    errors = [c for c in result.cases if c.outcome == "error"]
    assert len(errors) == 8 and all("scorer" in c.detail for c in errors)
    assert {c.case_id for c in result.cases if c.outcome == "pass"} == {"exact-reference", "unique-amount-no-reference"}
