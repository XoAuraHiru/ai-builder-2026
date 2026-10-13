"""Lead Score: the committed BigQuery ML model scored on synthetic leads it has never seen."""
from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, rate, suite
from app.ml.lead_history import generate_lead_history
from app.ml.lead_model import LeadModel, auc

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
