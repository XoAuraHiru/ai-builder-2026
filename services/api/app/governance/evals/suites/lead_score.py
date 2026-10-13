"""Lead Score: the committed BigQuery ML model scored on synthetic leads it has never seen, and on twin leads that
differ in one feature it weights positively."""
from decimal import Decimal

from app.governance import golden
from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, every_case, rate, run_case, suite
from app.governance.fairness import COUNTRIES, NAME_VARIANTS, variants
from app.ml.lead_history import generate_lead_history
from app.ml.lead_model import LeadModel, auc, score_lead
from app.models import Lead

# 5,000 leads: at 400 the AUC moves by about 0.03 between seeds, so a sound model could fail by chance.
HOLDOUT_SEED, HOLDOUT_SIZE, AUC_BAR = 2026, 5000, 0.75


@suite("lead_score")
def holdout_auc(ctx: EvalContext) -> SuiteResult:
    model = LeadModel.load()
    rows = generate_lead_history(n=HOLDOUT_SIZE, seed=HOLDOUT_SEED)  # training used seed 7
    labels = [r["converted"] for r in rows]
    scores = [model.probability({k: v for k, v in r.items() if k != "converted"}) for r in rows]
    value = auc(labels, scores)
    case = CaseResult("holdout-auc", "pass" if value >= AUC_BAR else "fail", expected=f"AUC at least {AUC_BAR}",
                      actual=round(value, 4), detail=f"{HOLDOUT_SIZE} synthetic leads from seed {HOLDOUT_SEED}")
    return rate("lead_score", "golden", "free", [case], bar=f"AUC at least {AUC_BAR} on {HOLDOUT_SIZE} held-out leads",
                metric=f"AUC {value:.2f} on {HOLDOUT_SIZE} held-out leads", value=value, threshold=AUC_BAR)


def _lead(fields: dict) -> Lead:
    values = {**fields}
    for money in ("investable_usd", "monthly_usd"):
        if money in values:
            values[money] = Decimal(str(values[money]))
    values.setdefault("full_name", "Twin")
    values.setdefault("country", "US")
    return Lead(**values)


@suite("lead_score")
def twin_pairs(ctx: EvalContext) -> SuiteResult:
    cases = []
    for c in golden.load("lead_score/twins")["cases"]:
        def check(c=c):
            strong, _ = score_lead(_lead(c["stronger"]), c.get("stronger_enrichment", c["enrichment"]))
            weak, _ = score_lead(_lead(c["weaker"]), c.get("weaker_enrichment", c["enrichment"]))
            ok = strong > weak
            return CaseResult(c["id"], "pass" if ok else "fail", expected="stronger > weaker",
                              actual={"stronger": strong, "weaker": weak}, detail=c["why"])
        cases.append(run_case(c["id"], check))
    return every_case("lead_score", "golden", "free", cases, bar="The stronger lead of every twin pair scores higher")


@suite("lead_score", kind="fairness")
def fair_lending(ctx: EvalContext) -> SuiteResult:
    """Twelve golden leads, each under six names and three countries: the score and its factors must not move."""
    cases = []
    for c in golden.load("fairness/leads")["cases"]:
        def check(c=c):
            seen: dict[tuple, list[str]] = {}
            for v in variants(c["fields"], NAME_VARIANTS, COUNTRIES):
                score, factors = score_lead(_lead(v), c["enrichment"])
                key = (score, repr(factors.get("for")), repr(factors.get("against")))
                seen.setdefault(key, []).append(f"{v['full_name']} ({v['country']})")
            same = len(seen) == 1
            actual = {"variants": sum(len(v) for v in seen.values()),
                      "scores": [{"score": key[0], "variants": names} for key, names in seen.items()]}
            return CaseResult(c["id"], "pass" if same else "fail", expected="one score for every variant",
                              actual=actual, detail=c["why"] if same else f"The score moved with the name or country. {c['why']}")
        cases.append(run_case(c["id"], check))
    return every_case("lead_score", "fairness", "free", cases,
                      bar="Every golden lead scores the same under six names and three countries")
