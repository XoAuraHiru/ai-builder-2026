from sqlalchemy import select

from app.ai.llm import FakeLLM
from app.models import AIDecision
from app.services.compliance import check_compliance

NO_FINDINGS = {"compliance_review": {"findings": []}}


def test_rules_catch_guarantees_and_promissory_language():
    report = check_compliance("Our fund is guaranteed to double your money, totally risk-free!", FakeLLM(NO_FINDINGS))
    rules = {f.rule for f in report.findings}
    assert not report.ok and {"guarantee", "promissory"} <= rules and report.reviewed_by == ["rules", "gemini"]


def test_gemini_findings_are_merged_and_deduplicated():
    llm = FakeLLM({"compliance_review": {"findings": [
        {"phrase": "guaranteed", "rule": "guarantee", "explanation": "dup", "suggestion": "remove"},
        {"phrase": "best fund in America", "rule": "unbalanced_performance", "explanation": "superlative",
         "suggestion": "Remove the superlative"}]}})
    report = check_compliance("This guaranteed plan is the best fund in America.", llm)
    phrases = [f.phrase.lower() for f in report.findings]
    assert phrases.count("guaranteed") == 1 and "best fund in america" in phrases


def test_falls_back_to_rules_when_gemini_fails():
    report = check_compliance("Act now, this is risk-free.", FakeLLM({}))
    assert report.reviewed_by == ["rules"] and {f.rule for f in report.findings} == {"urgency", "promissory"}


def test_clean_text_is_ok_and_records_decision_when_asked(db, make_lead):
    lead = make_lead()
    report = check_compliance("Thanks for your interest. Investing involves risk, including loss of principal.",
                              FakeLLM(NO_FINDINGS), db=db, subject_id=lead.id)
    assert report.ok and report.findings == []
    assert db.scalar(select(AIDecision)).purpose == "compliance_review"


def test_disclaimers_that_deny_a_guarantee_are_not_flagged():
    text = ("These numbers do not guarantee future returns. We can never promise or guarantee returns, "
            "and no investment is risk-free.")
    report = check_compliance(text, FakeLLM(NO_FINDINGS))
    assert report.ok, [f.phrase for f in report.findings]
    assert not check_compliance("Returns are guaranteed.", FakeLLM(NO_FINDINGS)).ok
