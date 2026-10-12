from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd

from app.models import Fund, FundConstituent
from app.services.risk_metrics import blended_band, risk_report


def fund(code, ticker, band):
    return Fund(code=code, name=code, category="growth", risk_band=band, fee_bps=0, min_investment=Decimal(0),
                objective="", who_for="", inception_on=date(2024, 10, 1),
                constituents=[FundConstituent(ticker=ticker, weight=Decimal(1), asset_class="equity", region="US",
                                              sector="broad")])


def market(n=60, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2010-01-01", periods=n, freq="MS")
    return pd.DataFrame({"SPY": rng.normal(0.008, 0.045, n), "BIL": np.full(n, 0.001),
                         "OTH": rng.normal(0.004, 0.02, n)}, index=idx)


def test_a_portfolio_that_is_the_market_has_beta_one():
    r = market()
    report = risk_report({"M": fund("M", "SPY", 4)}, {"M": 1.0}, 10_000, returns=r)
    assert report.beta == 1.0 and report.correlations == {"M": {"M": 1.0}}
    assert report.risk_contributions_pct == {"M": 100.0}
    assert report.annual_volatility_pct == round(r["SPY"].std(ddof=1) * np.sqrt(12) * 100, 1)


def test_drawdown_var_and_worst_month_follow_their_definitions():
    idx = pd.date_range("2010-01-01", periods=24, freq="MS")
    spy = [0.1, -0.5, 0.2] + [0.01] * 21
    r = pd.DataFrame({"SPY": spy, "BIL": [0.0] * 24}, index=idx)
    report = risk_report({"M": fund("M", "SPY", 4)}, {"M": 1.0}, 1000, returns=r)
    assert (report.max_drawdown_pct, report.drawdown_peak, report.drawdown_trough) == (-50.0, "2010-01", "2010-02")
    assert report.worst_month == {"month": "2010-02", "pct": -50.0}
    assert report.var95_1m_pct == round(-np.percentile(spy, 5) * 100, 1)
    assert report.var95_1m_usd == round(-np.percentile(spy, 5) * 1000, 2)


def test_risk_contributions_sum_to_100_and_bands_blend():
    funds = {"A": fund("A", "SPY", 5), "B": fund("B", "OTH", 3)}
    report = risk_report(funds, {"A": 0.5, "B": 0.5}, 10_000, returns=market())
    assert abs(sum(report.risk_contributions_pct.values()) - 100) < 0.2
    assert report.risk_contributions_pct["A"] > 50  # the more volatile fund carries more of the risk
    assert report.portfolio_band == 4 and blended_band(funds, {"A": 0.25, "B": 0.75}) == 4  # 3.5 rounds half up


def test_flat_returns_do_not_divide_by_zero():
    idx = pd.date_range("2010-01-01", periods=24, freq="MS")
    r = pd.DataFrame({"SPY": [0.01, -0.01] * 12, "BIL": [0.0] * 24, "FLAT": [0.0] * 24}, index=idx)
    report = risk_report({"F": fund("F", "FLAT", 1)}, {"F": 1.0}, 1000, returns=r)
    assert report.annual_volatility_pct == 0.0 and report.sharpe == 0.0
    assert report.correlations == {"F": {"F": 1.0}}
