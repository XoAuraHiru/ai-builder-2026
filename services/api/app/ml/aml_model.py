"""The AML anomaly model: k-means over how an account behaved in the last 90 days, in standardised units. An account far
from every cluster centre behaves unlike ordinary accounts. Trained offline (locally, or in BigQuery ML with
`python -m app.ml.train_aml_model --bigquery`) and committed, like the lead model, so scoring needs no network."""
from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

MODEL_PATH = Path(__file__).with_name("aml_model.json")
FEATURES = ("inflow_usd", "outflow_usd", "n_instructions", "n_orders", "max_single_usd", "distinct_payers")
LABELS = {"inflow_usd": "Paid in over 90 days", "outflow_usd": "Taken out over 90 days",
          "n_instructions": "Fund instructions", "n_orders": "Share orders",
          "max_single_usd": "Largest single movement", "distinct_payers": "Different payers"}


@dataclass
class AmlModel:
    centroids: list[list[float]]   # in standardised units, one per cluster
    means: dict[str, float]
    stds: dict[str, float]
    threshold: float               # the 99th percentile of ordinary accounts' distance to their nearest centre
    source: str                    # local | bigquery-ml
    model_name: str
    trained_at: str

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> "AmlModel":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self, path: Path = MODEL_PATH) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    def standardise(self, x: dict) -> list[float]:
        return [(float(x[f]) - self.means[f]) / (self.stds[f] or 1.0) for f in FEATURES]

    def distance(self, x: dict) -> float:
        z = self.standardise(x)
        return min(math.dist(z, c) for c in self.centroids)


def feature_history(n: int = 3000, seed: int = 7) -> list[dict]:
    """Synthetic 90-day behaviour of ordinary accounts: monthly savers across one to three funds, savers who also trade
    shares, people drawing an income, and occasional lump sums. The model learns what ordinary looks like here."""
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        funds = rng.choice([1, 1, 2, 2, 3])
        monthly = rng.uniform(200, 3500)
        inflow = monthly * 3 * rng.uniform(0.9, 1.1)
        outflow, orders = 0.0, 0
        instructions = 3 * funds + rng.randint(0, 2)
        biggest = monthly / funds * rng.uniform(1.0, 1.3)
        kind = rng.random()
        if kind < 0.25:                      # also trades shares
            orders = rng.randint(1, 12)
        elif kind < 0.45:                    # draws an income or takes a quarter of a holding out
            outflow = rng.uniform(1000, 9000)
            biggest = max(biggest, outflow / rng.choice([1, 2, 3]))
            instructions += rng.randint(1, 3)
        elif kind < 0.55:                    # an occasional lump sum
            lump = rng.uniform(5000, 25000)
            inflow += lump
            biggest = max(biggest, lump)
            instructions += 1
        rows.append({"inflow_usd": round(inflow, 2), "outflow_usd": round(outflow, 2),
                     "n_instructions": instructions, "n_orders": orders, "max_single_usd": round(biggest, 2),
                     "distinct_payers": 2 if rng.random() < 0.05 else 1})
    return rows


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def train_local(rows: list[dict], k: int = 4, seed: int = 7, iterations: int = 60) -> AmlModel:
    data = np.array([[r[f] for f in FEATURES] for r in rows], dtype=float)
    means, stds = data.mean(axis=0), data.std(axis=0)
    stds[stds == 0] = 1.0
    z = (data - means) / stds
    rng = np.random.default_rng(seed)
    centres = [z[rng.integers(len(z))]]
    for _ in range(1, k):  # k-means++ seeding
        nearest = np.min([((z - c) ** 2).sum(axis=1) for c in centres], axis=0)
        centres.append(z[rng.choice(len(z), p=nearest / nearest.sum())])
    centres = np.array(centres)
    for _ in range(iterations):
        labels = np.argmin(((z[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2), axis=1)
        moved = np.array([z[labels == j].mean(axis=0) if (labels == j).any() else centres[j] for j in range(k)])
        if np.allclose(moved, centres):
            break
        centres = moved
    distances = np.sqrt(((z[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2)).min(axis=1)
    return AmlModel(centroids=[[round(float(v), 6) for v in c] for c in centres],
                    means={f: round(float(m), 6) for f, m in zip(FEATURES, means)},
                    stds={f: round(float(s), 6) for f, s in zip(FEATURES, stds)},
                    threshold=round(float(np.percentile(distances, 99)), 6), source="local",
                    model_name="numpy k-means (local)", trained_at=_now())
