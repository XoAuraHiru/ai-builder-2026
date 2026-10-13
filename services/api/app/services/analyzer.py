"""Return analyzer: one Atrium fund (a unit trust) or one share, a one-time amount, a duration, and what it could become.

It runs the What-if engine (app/services/whatif.py) unchanged. A share is simulated as a one-constituent fund with no
fee over its own monthly history, and the S&P 500 (SPY) is simulated in the same call, so both face the same drawn
months. Shares are a list chosen today, so their histories flatter them; SPY beside them keeps that in view.

The rules below are the product's rules, checked here whatever the form allowed: a one-time amount is always needed,
monthly amounts are for unit trusts only (from the monthly-plan minimum), and a share needs ten years of history.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

import pandas as pd

from app.markets.universe import CASH, analytics_returns, instruments
from app.models import Fund, FundConstituent
from app.services.instructions import RECURRING_MINIMUM
from app.services.whatif import PATHS, Plan, ScenarioResult, WhatIfError, WhatIfResult, simulate

MIN_SHARE_MONTHS = 120
MAX_YEARS = 40
BENCHMARK = "SPY"
BENCHMARK_LABEL = "S&P 500 (SPY)"


class AnalyzerError(ValueError):
    """The request cannot be analysed; the message says why, in words the person can act on."""


@dataclass(frozen=True)
class AnalysisRequest:
    kind: Literal["unit_trust", "share"]
    code: str
    initial_usd: float
    monthly_usd: float
    years: int


@dataclass
class AnalysisResult:
    kind: str
    code: str
    name: str
    fee_bps: float
    min_investment: float
    result: WhatIfResult
    comparison: ScenarioResult | None


def usd(x) -> str:
    return f"${Decimal(str(x)):,.0f}"


def share_returns() -> pd.DataFrame:
    return analytics_returns().drop(columns=[CASH])


def share_names() -> dict[str, tuple[str, str]]:
    return {s: (i.name, i.kind) for s, i in instruments().items()}


def share_options(returns: pd.DataFrame | None = None,
                  names: dict[str, tuple[str, str]] | None = None) -> list[dict]:
    """Every quoted stock and ETF with at least ten years of monthly returns, in the universe's order."""
    r = share_returns() if returns is None else returns
    names = share_names() if names is None else names
    out = []
    for symbol, (name, kind) in names.items():
        if symbol not in r.columns:
            continue
        history = r[symbol].dropna()
        if len(history) >= MIN_SHARE_MONTHS:
            out.append({"symbol": symbol, "name": name, "kind": kind, "history_start": f"{history.index[0]:%Y-%m}"})
    return out


def _check_common(req: AnalysisRequest) -> None:
    if not req.initial_usd > 0:
        raise AnalyzerError("Enter a one-time amount to invest.")
    if not 1 <= req.years <= MAX_YEARS:
        raise AnalyzerError(f"Choose 1 to {MAX_YEARS} years.")
    if req.monthly_usd < 0:
        raise AnalyzerError("A monthly amount cannot be negative.")


def _share_fund(symbol: str, name: str) -> Fund:
    """The share as a fee-free, one-constituent fund, so the What-if engine runs it unchanged. Never persisted."""
    return Fund(code=symbol, name=name, category="share", risk_band=0, fee_bps=0, min_investment=Decimal("0"),
                objective="", who_for="", inception_on=date(2007, 6, 1),
                constituents=[FundConstituent(ticker=symbol, weight=Decimal("1"), asset_class="equity", region="US",
                                              sector="share")])


def _simulate(funds: dict[str, Fund], scenarios: list[tuple[str, dict[str, float]]], plan: Plan, paths: int,
              returns: pd.DataFrame | None) -> WhatIfResult:
    try:
        return simulate(funds, scenarios, plan, paths=paths, returns=returns)
    except WhatIfError as e:
        raise AnalyzerError(str(e)) from e


def analyze(funds: dict[str, Fund], req: AnalysisRequest, *, paths: int = PATHS,
            fund_returns_df: pd.DataFrame | None = None, share_returns_df: pd.DataFrame | None = None,
            names: dict[str, tuple[str, str]] | None = None) -> AnalysisResult:
    _check_common(req)
    plan = Plan(float(req.initial_usd), float(req.monthly_usd), int(req.years))

    if req.kind == "unit_trust":
        fund = funds.get(req.code)
        if fund is None:
            raise AnalyzerError("Choose one of Atrium's funds.")
        if Decimal(str(req.initial_usd)) < fund.min_investment:
            raise AnalyzerError(f"{fund.name} needs at least {usd(fund.min_investment)} to start.")
        if 0 < req.monthly_usd < RECURRING_MINIMUM:
            raise AnalyzerError(f"Monthly amounts start at {usd(RECURRING_MINIMUM)}.")
        result = _simulate(funds, [(fund.name, {fund.code: 1.0})], plan, paths, fund_returns_df)
        return AnalysisResult(kind=req.kind, code=fund.code, name=fund.name, fee_bps=float(fund.fee_bps),
                              min_investment=float(fund.min_investment), result=result, comparison=None)

    if req.kind != "share":
        raise AnalyzerError("Choose a unit trust or shares.")
    if req.monthly_usd:
        raise AnalyzerError("Monthly amounts are for unit trusts only; shares take a one-time amount.")
    symbol = req.code.strip().upper()
    r = share_returns() if share_returns_df is None else share_returns_df
    if symbol not in r.columns:
        raise AnalyzerError(f"{symbol} is not one of the shares Atrium quotes.")
    if len(r[symbol].dropna()) < MIN_SHARE_MONTHS:
        raise AnalyzerError(f"{symbol} has too little history to simulate; it needs ten years of monthly prices.")
    name = (share_names() if names is None else names).get(symbol, (symbol,))[0]
    pool = {symbol: _share_fund(symbol, name)}
    scenarios = [(name, {symbol: 1.0})]
    if symbol != BENCHMARK:
        pool[BENCHMARK] = _share_fund(BENCHMARK, BENCHMARK_LABEL)
        scenarios.append((BENCHMARK_LABEL, {BENCHMARK: 1.0}))
    result = _simulate(pool, scenarios, plan, paths, r)
    comparison = result.scenarios.pop(1) if len(result.scenarios) > 1 else None
    return AnalysisResult(kind=req.kind, code=symbol, name=name, fee_bps=0.0, min_investment=0.0, result=result,
                          comparison=comparison)
