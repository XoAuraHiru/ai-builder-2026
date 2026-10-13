"""Free-tier golden suites: each passes on the committed code, and each fails when its model is broken."""
import pytest

from app.governance import golden
from app.governance.evals.framework import EvalContext
from app.governance.evals.suites import aml_scenarios, lead_score, trust_rules

FREE = EvalContext(tier="free")


def test_every_golden_case_says_why_its_answer_is_right():
    for name in ("lead_score/twins", "trust_rules/stories", "aml_scenarios/cases"):
        data = golden.load(name)
        assert data["cases"] and all(c.get("why") for c in data["cases"]), name


def test_a_golden_file_with_a_case_missing_its_why_is_refused(tmp_path, monkeypatch):
    (tmp_path / "bad.json").write_text('{"cases": [{"id": "a", "why": "fine"}, {"id": "b"}]}', encoding="utf-8")
    monkeypatch.setattr(golden, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="b"):
        golden.load("bad")


def test_the_stronger_twin_always_outscores_the_weaker():
    result = lead_score.twin_pairs(FREE)
    assert result.passed and len(result.cases) == 8, [c.detail for c in result.cases if c.outcome != "pass"]


def test_twins_fail_when_the_model_ranks_backwards(monkeypatch):
    monkeypatch.setattr(lead_score, "score_lead", lambda lead, enrichment: (100 - int(lead.investable_usd > 50000) * 60, {}))
    assert lead_score.twin_pairs(FREE).passed is False


def test_the_demo_fraud_stories_are_caught_and_genuine_leads_stay_clear():
    result = trust_rules.demo_stories(FREE)
    assert result.passed, [c.detail for c in result.cases if c.outcome != "pass"]
    assert {c.case_id for c in result.cases} >= {"alex-mercer", "device-ring", "m-chen"}
    assert len(result.cases) == 9


def test_the_stories_fail_when_the_throwaway_list_is_emptied(monkeypatch):
    import app.services.trust as trust

    monkeypatch.setattr(trust, "DISPOSABLE_DOMAINS", frozenset())
    assert trust_rules.demo_stories(FREE).passed is False


def test_each_aml_scenario_fires_on_its_case_and_not_on_its_near_miss():
    result = aml_scenarios.positives_and_near_misses(FREE)
    assert result.passed and len(result.cases) == 14, [c.detail for c in result.cases if c.outcome != "pass"]
    assert {c["scenario"] for c in golden.load("aml_scenarios/cases")["cases"]} == set(aml_scenarios.SCENARIOS)


def test_a_scenario_that_never_fires_fails_its_positive(monkeypatch):
    monkeypatch.setitem(aml_scenarios.SCENARIOS, "structuring", lambda db, today: [])
    result = aml_scenarios.positives_and_near_misses(FREE)
    assert [c.case_id for c in result.cases if c.outcome == "fail"] == ["structuring-positive"]
