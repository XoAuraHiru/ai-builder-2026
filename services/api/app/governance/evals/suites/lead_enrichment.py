"""Lead enrichment (Gemini Flash): ten golden leads, graded on the goal category, the suggested funds and whether the
planted inconsistencies are found."""
from decimal import Decimal

from app.governance import golden
from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, rate, run_case, scratch_db, share_passing, suite
from app.models import Lead
from app.seed.funds import seed_funds
from app.services.enrichment import enrich_lead

ENRICHMENT_BAR = 0.8
FOUND = ("medium", "high")  # a low-severity remark is not a contradiction the advisor must resolve


def make_lead(db, fields: dict, n: int) -> Lead:
    values = {**fields}
    for money in ("investable_usd", "monthly_usd"):
        values[money] = Decimal(str(values.get(money, "0")))
    values.setdefault("email", f"golden.lead{n}@example.test")
    values.setdefault("phone", f"+1415555{n:04d}")
    values.setdefault("country", "US")
    values.setdefault("device_id", f"golden-device-{n}")
    lead = Lead(**values)
    db.add(lead)
    db.flush()
    return lead


def grade(c: dict, enrichment) -> CaseResult:
    expect = c["expect"]
    inconsistent = any(i.severity in FOUND for i in enrichment.consistency_issues)
    problems = []
    if enrichment.goal_category not in expect["goal_category"]:
        problems.append(f"goal category {enrichment.goal_category}, expected one of {', '.join(expect['goal_category'])}")
    outside = [f for f in enrichment.suggested_funds if f not in expect["allowed_funds"]]
    if outside:
        problems.append(f"suggested {', '.join(outside)}, outside {', '.join(expect['allowed_funds'])}")
    if inconsistent != expect["inconsistent"]:
        problems.append("missed the planted inconsistency" if expect["inconsistent"]
                        else "reported an inconsistency that is not there")
    actual = {"goal_category": enrichment.goal_category, "suggested_funds": enrichment.suggested_funds,
              "inconsistent": inconsistent, "issues": [i.issue for i in enrichment.consistency_issues]}
    detail = c["why"] if not problems else f"{'; '.join(problems).capitalize()}. {c['why']}"
    return CaseResult(c["id"], "fail" if problems else "pass", expected=expect, actual=actual, detail=detail)


@suite("lead_enrichment", tier="live")
def golden_leads(ctx: EvalContext) -> SuiteResult:
    cases = []
    with scratch_db() as db:
        seed_funds(db)
        db.flush()
        for n, c in enumerate(golden.load("lead_enrichment/leads")["cases"], start=1):
            lead = make_lead(db, c["fields"], n)
            cases.append(run_case(c["id"], lambda c=c, lead=lead: grade(c, enrich_lead(db, lead, ctx.llm)), db=db))
    value = share_passing(cases)
    passed = sum(c.outcome == "pass" for c in cases)
    judged = sum(c.outcome != "error" for c in cases)
    return rate("lead_enrichment", "golden", "live", cases,
                bar=f"At least {ENRICHMENT_BAR:.0%} of the ten golden leads read right: goal, funds and inconsistencies",
                metric=f"{passed} of {judged} leads read right", value=value, threshold=ENRICHMENT_BAR)
