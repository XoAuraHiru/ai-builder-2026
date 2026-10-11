from decimal import Decimal

import numpy as np

from app.ml.lead_features import FEATURES, LABELS, features_for
from app.ml.lead_history import TRUE_WEIGHTS, generate_lead_history
from app.ml.lead_model import LeadModel, auc, score_lead, train_local


def test_history_is_deterministic_with_plausible_base_rate():
    a, b = generate_lead_history(400, seed=3), generate_lead_history(400, seed=3)
    assert a == b and set(a[0]) == set(FEATURES) | {"converted"}
    rate = np.mean([r["converted"] for r in a])
    assert 0.2 < rate < 0.5


def test_local_training_recovers_signs_and_ranks_holdout_well():
    rows = generate_lead_history(1200, seed=11)
    model = train_local(rows[:900])
    for f, w in TRUE_WEIGHTS.items():
        assert np.sign(model.weights[f]) == np.sign(w), f
    holdout = rows[900:]
    assert auc([r["converted"] for r in holdout], [model.probability(r) for r in holdout]) > 0.7


def test_model_round_trips_through_json(tmp_path):
    model = train_local(generate_lead_history(300, seed=5))
    path = tmp_path / "m.json"
    model.save(path)
    again = LeadModel.load(path)
    x = generate_lead_history(1, seed=99)[0]
    assert again.probability(x) == model.probability(x) and again.source == "local"


def test_features_for_lead(make_lead):
    lead = make_lead(source="referral", notes="Looking for a long-term plan for my family", phone="+14155550123")
    x = features_for(lead, {"suggested_funds": ["ATR-GRW"]})
    assert x["referral"] == 1.0 and x["has_phone"] == 1.0 and x["goal_fit"] == 1.0
    assert x["completeness"] == 1.0 and abs(x["horizon"] - 20 / 30) < 1e-9
    assert features_for(make_lead(phone="555-1234", email="b@example.test"), None)["has_phone"] == 0.0


def test_committed_artifact_scores_and_explains(make_lead):
    score, factors = score_lead(make_lead(), {"suggested_funds": ["ATR-BAL"]})
    assert 0 <= score <= 100 and factors["model"] and factors["source"] in ("local", "bigquery-ml")
    assert factors["for"] and all(f["impact"] > 0 for f in factors["for"])
    assert all(f["impact"] < 0 for f in factors["against"])
    assert all(f["label"] in LABELS.values() and f["value"] for f in factors["for"] + factors["against"])


def test_more_investable_never_lowers_score(make_lead):
    low, _ = score_lead(make_lead(investable_usd=Decimal("10000")), None)
    high, _ = score_lead(make_lead(investable_usd=Decimal("500000"), email="c@example.test"), None)
    assert high >= low
