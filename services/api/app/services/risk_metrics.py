"""Risk analytics (B4) for a portfolio, from the committed monthly history of its funds since 2007."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.models import Fund
from app.services.fund_returns import benchmark_returns, fund_return_frame, riskfree_returns


@dataclass
class RiskReport:
    window_start: str
    window_end: str
    months: int
    weights: dict[str, float]
    value_usd: float
    annual_volatility_pct: float
    beta: float
    max_drawdown_pct: float
    drawdown_peak: str
    drawdown_trough: str
    var95_1m_pct: float
    var95_1m_usd: float
    sharpe: float
    worst_month: dict
    best_month: dict
    correlations: dict[str, dict[str, float]]
    risk_contributions_pct: dict[str, float]
    portfolio_band: int


def blended_band(funds: dict[str, Fund], weights: dict[str, float]) -> int:
    """Value-weighted average of the funds' risk bands, rounded half up."""
    total = sum(weights.values())
    return int(math.floor(sum(w / total * funds[c].risk_band for c, w in weights.items()) + 0.5))


def risk_report(funds: dict[str, Fund], weights: dict[str, float], value_usd: float,
                returns: pd.DataFrame | None = None) -> RiskReport:
    codes = sorted(weights)
    frame = fund_return_frame(funds, codes, returns)
    aligned = (frame.join(benchmark_returns(returns).rename("_bench"), how="inner")
               .join(riskfree_returns(returns).rename("_rf"), how="inner"))
    r = aligned[codes]
    w = np.array([weights[c] for c in codes], dtype="float64")
    w = w / w.sum()
    port = pd.Series(r.to_numpy() @ w, index=r.index)
    bench = aligned["_bench"]
    vol = float(port.std(ddof=1)) * math.sqrt(12)
    bench_var = float(bench.var(ddof=1))
    beta = float(port.cov(bench)) / bench_var if bench_var > 0 else 0.0
    wealth = (1 + port).cumprod()
    drawdown = wealth / wealth.cummax() - 1
    trough = drawdown.idxmin()
    peak = wealth.loc[:trough].idxmax()
    var95 = -float(np.percentile(port, 5))
    sharpe = float((port - aligned["_rf"]).mean() * 12 / vol) if vol > 1e-12 else 0.0
    cov = r.cov().to_numpy()
    sigma2 = float(w @ cov @ w)
    contributions = (w * (cov @ w)) / sigma2 if sigma2 > 1e-18 else w
    corr = r.corr().fillna(0.0)
    for c in codes:
        corr.loc[c, c] = 1.0
    return RiskReport(
        window_start=f"{r.index[0]:%Y-%m}", window_end=f"{r.index[-1]:%Y-%m}", months=len(r),
        weights={c: round(float(x), 4) for c, x in zip(codes, w)}, value_usd=round(value_usd, 2),
        annual_volatility_pct=round(vol * 100, 1), beta=round(beta, 2), max_drawdown_pct=round(float(drawdown.min()) * 100, 1),
        drawdown_peak=f"{peak:%Y-%m}", drawdown_trough=f"{trough:%Y-%m}", var95_1m_pct=round(var95 * 100, 1),
        var95_1m_usd=round(var95 * value_usd, 2), sharpe=round(sharpe, 2),
        worst_month={"month": f"{port.idxmin():%Y-%m}", "pct": round(float(port.min()) * 100, 1)},
        best_month={"month": f"{port.idxmax():%Y-%m}", "pct": round(float(port.max()) * 100, 1)},
        correlations={c: {d: round(float(corr.loc[c, d]), 2) for d in codes} for c in codes},
        risk_contributions_pct={c: round(float(x) * 100, 1) for c, x in zip(codes, contributions)},
        portfolio_band=blended_band(funds, dict(zip(codes, w))))
