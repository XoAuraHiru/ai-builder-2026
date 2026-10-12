"""Monthly returns for house funds and mixes of them, from the committed long history.

Before a constituent ETF existed, its weight is spread across the fund's other ETFs that did, so every house fund has
a continuous backtest from mid-2007. backfill_notes says exactly where that happened, for the fund documents.
"""
from __future__ import annotations

import pandas as pd

from app.models import Fund
from app.seed.history import BENCHMARK, RISK_FREE, load_monthly_history


def monthly_returns(prices: pd.DataFrame | None = None) -> pd.DataFrame:
    """Month-on-month returns. A ticker's first month with a price has no return yet (NaN)."""
    p = load_monthly_history() if prices is None else prices
    return (p / p.shift(1) - 1).iloc[1:]


def constituent_weights(fund: Fund) -> dict[str, float]:
    return {c.ticker: float(c.weight) for c in fund.constituents}


def fund_returns(weights: dict[str, float], returns: pd.DataFrame | None = None) -> pd.Series:
    r = (monthly_returns() if returns is None else returns)[list(weights)]
    present = r.notna()
    w = present.mul(pd.Series(weights, dtype="float64"), axis=1)
    total = w.sum(axis=1)
    out = (r.fillna(0.0) * w).sum(axis=1) / total.where(total > 0)
    return out.dropna()


def fund_return_frame(funds: dict[str, Fund], codes: list[str], returns: pd.DataFrame | None = None) -> pd.DataFrame:
    """One column of monthly returns per fund, over the months every one of them has."""
    return pd.DataFrame({c: fund_returns(constituent_weights(funds[c]), returns) for c in codes}).dropna()


def mix_returns(funds: dict[str, Fund], allocation: dict[str, float], returns: pd.DataFrame | None = None) -> pd.Series:
    """Monthly returns of a fixed mix of house funds, rebalanced monthly."""
    frame = fund_return_frame(funds, list(allocation), returns)
    weights = pd.Series(allocation, dtype="float64")
    return (frame * (weights / weights.sum())).sum(axis=1)


def benchmark_returns(returns: pd.DataFrame | None = None) -> pd.Series:
    return (monthly_returns() if returns is None else returns)[BENCHMARK].dropna()


def riskfree_returns(returns: pd.DataFrame | None = None) -> pd.Series:
    return (monthly_returns() if returns is None else returns)[RISK_FREE].dropna()


def backfill_notes(fund: Fund, prices: pd.DataFrame | None = None) -> list[str]:
    p = load_monthly_history() if prices is None else prices
    starts = {c.ticker: p[c.ticker].first_valid_index() for c in fund.constituents}
    first = min(starts.values())
    r = fund_returns(constituent_weights(fund), monthly_returns(p))
    notes = [f"The backtest starts in {r.index[0]:%B %Y}."]
    for c in sorted(fund.constituents, key=lambda c: c.ticker):
        if starts[c.ticker] > first:
            notes.append(f"{c.ticker} has prices from {starts[c.ticker]:%B %Y}; before that, its {float(c.weight):.0%} "
                         "weight is spread across the fund's other ETFs.")
    return notes
