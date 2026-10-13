"""Draft compliance check: the phrase rules catch the golden promises and spare the honest sentences (free); Gemini
agrees with the golden labels (live)."""
from app.governance import golden
from app.governance.evals.framework import (CaseResult, EvalContext, SuiteResult, every_case, rate, run_case, scratch_db,
                                            share_passing, suite)
from app.services import compliance


@suite("draft_compliance")
def rules_on_phrases(ctx: EvalContext) -> SuiteResult:
    cases = []
    for c in golden.load("draft_compliance/phrases")["cases"]:
        def check(c=c):
            found = compliance._rule_findings(c["text"])
            flagged = bool(found)
            return CaseResult(c["id"], "pass" if flagged == c["promissory"] else "fail",
                              expected={"flagged": c["promissory"]},
                              actual={"flagged": flagged, "phrases": [f.phrase for f in found]}, detail=c["why"])
        cases.append(run_case(c["id"], check))
    return every_case("draft_compliance", "golden", "free", cases,
                      bar="The rules flag all five promises and none of the five honest sentences")


GEMINI_BAR = 0.9
PROMISE_RULES = ("guarantee", "promissory")


@suite("draft_compliance", tier="live")
def gemini_on_phrases(ctx: EvalContext) -> SuiteResult:
    """Gemini's own findings, apart from the rules', on each golden sentence."""
    cases = []
    with scratch_db() as db:
        for c in golden.load("draft_compliance/phrases")["cases"]:
            def check(c=c):
                collected: list = []
                report = compliance.check_compliance(c["text"], ctx.llm, db=db, subject_id=f"golden-{c['id']}",
                                                     collect=collected)
                if "gemini" not in report.reviewed_by:
                    return CaseResult(c["id"], "error", detail="Gemini could not be reached; only the rules ran.")
                # The golden label is about promises; a performance or disclosure remark on an honest sentence is
                # Gemini covering other parts of the Marketing Rule, not a disagreement.
                found = [f for f in collected[0][0].parsed.findings if f.rule in PROMISE_RULES]
                flagged = bool(found)
                return CaseResult(c["id"], "pass" if flagged == c["promissory"] else "fail",
                                  expected={"flagged": c["promissory"]},
                                  actual={"flagged": flagged, "phrases": [f.phrase for f in found]}, detail=c["why"])
            cases.append(run_case(c["id"], check, db=db))
    agreed = sum(c.outcome == "pass" for c in cases)
    return rate("draft_compliance", "golden", "live", cases,
                bar=f"Gemini flags a guarantee or a promise exactly where the golden label says, on at least "
                    f"{GEMINI_BAR:.0%} of ten sentences",
                metric=f"Gemini agreed on {agreed} of {len(cases)} sentences", value=share_passing(cases),
                threshold=GEMINI_BAR)
