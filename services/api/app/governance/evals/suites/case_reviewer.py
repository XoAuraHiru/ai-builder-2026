"""Case review: the deterministic checkers catch every planted fault in a recorded review (free); Gemini Pro's reviews
of five golden alerts, and Flash's as a challenger (live)."""
from app.ai.figures import collect_figures
from app.governance import golden
from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, every_case, run_case, suite
from app.services.compliance_ai import check_review


@suite("case_reviewer")
def checkers_catch_faults(ctx: EvalContext) -> SuiteResult:
    data = golden.load("case_reviewer/recorded")
    facts = data["facts"]
    evidence_ids = {e["id"] for e in facts["evidence"]}
    figures, names = collect_figures(facts), set(data["names"])
    cases = []
    for c in data["cases"]:
        def check(c=c):
            found = check_review(c["review"], evidence_ids, figures, names)
            return CaseResult(c["id"], "pass" if found == c["expect"] else "fail", expected=c["expect"], actual=found,
                              detail=c["why"])
        cases.append(run_case(c["id"], check))
    return every_case("case_reviewer", "golden", "free", cases,
                      bar="The clean review passes, and every planted fault (a false citation, an invented figure, a "
                          "person not in the inputs) is caught")
