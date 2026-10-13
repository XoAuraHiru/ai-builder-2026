"""Draft compliance check: the phrase rules catch the golden promises and spare the honest sentences (free); Gemini
agrees with the golden labels (live)."""
from app.governance import golden
from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, every_case, run_case, suite
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
