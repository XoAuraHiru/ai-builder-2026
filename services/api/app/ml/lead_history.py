"""Synthetic conversion history for training. The ground truth is a known logistic model, so tests can check recovery."""
import math

import numpy as np

TRUE_INTERCEPT = -9.6
TRUE_WEIGHTS = {"log_investable": 1.1, "log_monthly": 0.35, "horizon": 0.9, "referral": 1.2, "has_phone": 0.6,
                "completeness": 1.4, "goal_fit": 1.0}


def generate_lead_history(n: int = 800, seed: int = 7) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    for _ in range(n):
        investable = float(np.exp(rng.normal(math.log(60_000), 1.2)))
        monthly = float(max(0.0, rng.normal(800, 700)))
        x = {"log_investable": round(math.log10(1 + investable), 6),
             "log_monthly": round(math.log10(1 + monthly), 6),
             "horizon": round(int(rng.integers(0, 31)) / 30, 6), "referral": float(rng.random() < 0.25),
             "has_phone": float(rng.random() < 0.7), "completeness": int(rng.integers(0, 5)) / 4,
             "goal_fit": float(rng.random() < 0.75)}
        z = TRUE_INTERCEPT + sum(TRUE_WEIGHTS[k] * v for k, v in x.items()) + rng.normal(0, 0.5)
        x["converted"] = int(rng.random() < 1 / (1 + math.exp(-z)))
        rows.append(x)
    return rows
