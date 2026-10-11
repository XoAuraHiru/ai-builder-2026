import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.ml.lead_features import FEATURES, LABELS, describe, features_for

MODEL_PATH = Path(__file__).with_name("lead_model.json")


@dataclass
class LeadModel:
    intercept: float
    weights: dict[str, float]
    means: dict[str, float]
    source: str  # "local" or "bigquery-ml"
    model_name: str
    auc: float | None
    trained_at: str

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> "LeadModel":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self, path: Path = MODEL_PATH) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    def probability(self, x: dict[str, float]) -> float:
        z = self.intercept + sum(self.weights[f] * x[f] for f in FEATURES)
        return 1 / (1 + math.exp(-z))

    def score(self, x: dict[str, float]) -> int:
        return int(round(100 * self.probability(x)))

    def explain(self, x: dict[str, float], lead, top: int = 3) -> dict:
        """Linear-model attributions: weight times distance from the training mean (what ML.EXPLAIN_PREDICT reports)."""
        impacts = sorted(((f, self.weights[f] * (x[f] - self.means[f])) for f in FEATURES), key=lambda t: -t[1])

        def item(f: str, impact: float) -> dict:
            value = describe(f, lead) if f != "goal_fit" else ("yes" if x[f] else "not assessed yet, or no fit")
            return {"feature": f, "label": LABELS[f], "value": value, "impact": round(impact, 3)}

        return {"for": [item(f, i) for f, i in impacts if i > 0][:top],
                "against": [item(f, i) for f, i in reversed(impacts) if i < 0][:top]}


def auc(y: list[int], p: list[float]) -> float:
    """Probability that a random positive outranks a random negative (ties count half)."""
    pos = [s for s, t in zip(p, y) if t == 1]
    neg = [s for s, t in zip(p, y) if t == 0]
    if not pos or not neg:
        return float("nan")
    wins = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return wins / (len(pos) * len(neg))


def train_local(rows: list[dict], l2: float = 1e-3, iterations: int = 30) -> LeadModel:
    """Newton-Raphson logistic regression; the offline twin of the BigQuery ML model."""
    X = np.array([[1.0] + [r[f] for f in FEATURES] for r in rows])
    y = np.array([r["converted"] for r in rows], dtype=float)
    w = np.zeros(X.shape[1])
    reg = l2 * np.eye(X.shape[1])
    reg[0, 0] = 0.0
    for _ in range(iterations):
        p = 1 / (1 + np.exp(-X @ w))
        gradient = X.T @ (y - p) - reg @ w
        hessian = X.T @ (X * (p * (1 - p))[:, None]) + reg
        w = w + np.linalg.solve(hessian, gradient)
    model = LeadModel(intercept=float(w[0]), weights={f: float(v) for f, v in zip(FEATURES, w[1:])},
                      means={f: float(X[:, i + 1].mean()) for i, f in enumerate(FEATURES)}, source="local",
                      model_name="atrium-lead-conversion-local", auc=None,
                      trained_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    model.auc = round(auc(y.astype(int).tolist(), [model.probability(r) for r in rows]), 4)
    return model


_model: LeadModel | None = None


def score_lead(lead, enrichment: dict | None) -> tuple[int, dict]:
    global _model
    if _model is None:
        _model = LeadModel.load()
    x = features_for(lead, enrichment)
    return _model.score(x), {**_model.explain(x, lead), "model": _model.model_name, "source": _model.source,
                             "probability": round(_model.probability(x), 4)}
