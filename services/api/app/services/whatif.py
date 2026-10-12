"""What-if Studio engine (B6): Monte Carlo over real monthly history, deterministic and explainable.

Each simulated path is stitched from 12-month blocks of consecutive historical months drawn at random (a circular
block bootstrap), so crashes and recoveries keep their real shape. Every scenario in one request uses the same drawn
months, so a comparison is fair: two funds face the same simulated markets. The house-fund fee is taken monthly; ETF
costs are already in the prices. Same inputs, same answer: the random seed comes from the inputs.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from app.models import Fund
from app.services.fund_returns import fund_return_frame

PATHS = 10_000
BLOCK = 12
PERCENTILES = (10, 25, 50, 75, 90)
MAX_SCENARIOS = 3


class WhatIfError(ValueError):
    pass


@dataclass(frozen=True)
class Plan:
    initial: float
    monthly: float
    years: int
    goal: float | None = None


@dataclass
class ScenarioResult:
    label: str
    allocation: dict[str, float]
    fee_bps: float
    yearly: list[dict]
    final: dict[str, float]
    prob_goal: float | None
    prob_loss: float
    median_without_fees: float
    fee_cost: float
    history: dict


@dataclass
class WhatIfResult:
    plan: Plan
    contributed: float
    window_start: str
    window_end: str
    months: int
    paths: int
    scenarios: list[ScenarioResult] = field(default_factory=list)


def stable_seed(payload: dict) -> int:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return int(digest[:8], 16)


def draw_months(n_history: int, n_months: int, paths: int, rng: np.random.Generator, block: int = BLOCK) -> np.ndarray:
    """Indexes into the history, shape (paths, n_months): runs of `block` consecutive months, wrapping at the end."""
    n_blocks = math.ceil(n_months / block)
    starts = rng.integers(0, n_history, size=(paths, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n_history
    return idx.reshape(paths, n_blocks * block)[:, :n_months]


def grow(returns: np.ndarray, plan: Plan, fee_monthly: float) -> np.ndarray:
    """Value at each year end, shape (paths, years + 1). Contributions arrive at the start of every month."""
    paths, n_months = returns.shape
    value = np.full(paths, float(plan.initial))
    out = np.empty((paths, plan.years + 1))
    out[:, 0] = plan.initial
    for m in range(n_months):
        value = (value + plan.monthly) * (1.0 + returns[:, m] - fee_monthly)
        if (m + 1) % 12 == 0:
            out[:, (m + 1) // 12] = value
    return out


def history_stats(r: pd.Series) -> dict:
    wealth = (1 + r).cumprod()
    drawdown = wealth / wealth.cummax() - 1
    rolling = (1 + r).rolling(12).apply(np.prod, raw=True) - 1
    years = len(r) / 12
    return {
        "annual_return_pct": round((float(wealth.iloc[-1]) ** (1 / years) - 1) * 100, 1),
        "annual_volatility_pct": round(float(r.std(ddof=1)) * math.sqrt(12) * 100, 1),
        "worst_12m_pct": round(float(rolling.min()) * 100, 1),
        "best_12m_pct": round(float(rolling.max()) * 100, 1),
        "max_drawdown_pct": round(float(drawdown.min()) * 100, 1),
    }


def simulate(funds: dict[str, Fund], scenarios: list[tuple[str, dict[str, float]]], plan: Plan,
             paths: int = PATHS, returns: pd.DataFrame | None = None) -> WhatIfResult:
    if not 1 <= len(scenarios) <= MAX_SCENARIOS:
        raise WhatIfError(f"compare one to {MAX_SCENARIOS} scenarios")
    codes = sorted({code for _, allocation in scenarios for code in allocation})
    unknown = [c for c in codes if c not in funds]
    if unknown:
        raise WhatIfError(f"unknown fund: {', '.join(unknown)}")
    frame = fund_return_frame(funds, codes, returns)
    if len(frame) < 24:
        raise WhatIfError("not enough price history to simulate these funds")
    n_months = plan.years * 12
    seed = stable_seed({"plan": asdict(plan), "scenarios": scenarios, "paths": paths, "months": len(frame)})
    idx = draw_months(len(frame), n_months, paths, np.random.default_rng(seed))
    contributed = [plan.initial + plan.monthly * 12 * y for y in range(plan.years + 1)]
    result = WhatIfResult(plan=plan, contributed=round(contributed[-1], 2), window_start=f"{frame.index[0]:%Y-%m}",
                          window_end=f"{frame.index[-1]:%Y-%m}", months=len(frame), paths=paths)
    history = frame.to_numpy()
    for label, allocation in scenarios:
        total = sum(allocation.values())
        weights = np.array([allocation.get(c, 0.0) / total for c in frame.columns])
        mix = history @ weights
        fee_bps = sum(allocation[c] / total * funds[c].fee_bps for c in allocation)
        sampled = mix[idx]
        with_fees = grow(sampled, plan, fee_bps / 10_000 / 12)
        without_fees = grow(sampled, plan, 0.0)
        pct = np.percentile(with_fees, PERCENTILES, axis=0)
        yearly = [{"year": y, **{f"p{p}": round(float(pct[i, y]), 2) for i, p in enumerate(PERCENTILES)},
                   "contributed": round(contributed[y], 2)} for y in range(plan.years + 1)]
        final = with_fees[:, -1]
        median_without = float(np.median(without_fees[:, -1]))
        result.scenarios.append(ScenarioResult(
            label=label, allocation={c: round(allocation[c] / total, 4) for c in allocation}, fee_bps=round(fee_bps, 1),
            yearly=yearly, final={f"p{p}": round(float(pct[i, -1]), 2) for i, p in enumerate(PERCENTILES)},
            prob_goal=None if plan.goal is None else round(float((final >= plan.goal).mean()) * 100, 1),
            prob_loss=round(float((final < contributed[-1] - 0.005).mean()) * 100, 1),
            median_without_fees=round(median_without, 2), fee_cost=round(median_without - float(np.median(final)), 2),
            history={**history_stats(pd.Series(mix, index=frame.index)),
                     "window_start": result.window_start, "window_end": result.window_end}))
    return result
