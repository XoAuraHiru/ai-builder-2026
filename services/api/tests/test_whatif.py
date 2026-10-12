from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from app.models import Fund, FundConstituent
from app.services.whatif import Plan, WhatIfError, draw_months, simulate


def fund(code, ticker, fee_bps=0, band=3):
    return Fund(code=code, name=f"Fund {code}", category="balanced", risk_band=band, fee_bps=fee_bps,
                min_investment=Decimal("0"), objective="", who_for="", inception_on=date(2024, 10, 1),
                constituents=[FundConstituent(ticker=ticker, weight=Decimal("1"), asset_class="equity", region="US",
                                              sector="broad")])


def returns_frame(**sequences):
    """Monthly ETF returns exactly as given, one column per ticker."""
    n = len(next(iter(sequences.values())))
    idx = pd.date_range("2010-01-01", periods=n, freq="MS")
    return pd.DataFrame(sequences, index=idx, dtype="float64")


def test_constant_returns_give_one_certain_outcome():
    r = returns_frame(AAA=[0.01] * 60)
    out = simulate({"F": fund("F", "AAA")}, [("F", {"F": 1.0})], Plan(1000, 0, 2), paths=200, returns=r)
    final = out.scenarios[0].final
    assert final["p10"] == final["p50"] == final["p90"] == round(1000 * 1.01 ** 24, 2)
    assert out.scenarios[0].fee_cost == 0


def test_monthly_contributions_arrive_at_the_start_of_each_month():
    r = returns_frame(AAA=[0.0] * 60)
    out = simulate({"F": fund("F", "AAA")}, [("F", {"F": 1.0})], Plan(0, 100, 3), paths=50, returns=r)
    s = out.scenarios[0]
    assert out.contributed == 3600 and s.final["p50"] == 3600
    assert [p["contributed"] for p in s.yearly] == [0, 1200, 2400, 3600]
    assert s.prob_loss == 0


def test_fees_are_taken_monthly_and_their_cost_is_reported():
    r = returns_frame(AAA=[0.01] * 60)
    out = simulate({"F": fund("F", "AAA", fee_bps=120)}, [("F", {"F": 1.0})], Plan(1000, 0, 2), paths=50, returns=r)
    s = out.scenarios[0]
    assert s.final["p50"] == round(1000 * 1.009 ** 24, 2)
    assert s.fee_cost == round(1000 * 1.01 ** 24 - 1000 * 1.009 ** 24, 2)


def test_outcomes_are_ordered_repeatable_and_goal_aware():
    rng = np.random.default_rng(7)
    r = returns_frame(AAA=list(rng.normal(0.006, 0.04, 180)))
    funds = {"F": fund("F", "AAA")}
    plan = Plan(10_000, 300, 10, goal=60_000)
    a = simulate(funds, [("F", {"F": 1.0})], plan, paths=2000, returns=r)
    b = simulate(funds, [("F", {"F": 1.0})], plan, paths=2000, returns=r)
    assert a.scenarios[0].yearly == b.scenarios[0].yearly
    for p in a.scenarios[0].yearly:
        assert p["p10"] <= p["p25"] <= p["p50"] <= p["p75"] <= p["p90"]
    assert 0 < a.scenarios[0].prob_goal < 100 and len(a.scenarios[0].yearly) == 11


def test_scenarios_face_the_same_simulated_markets():
    rng = np.random.default_rng(3)
    r = returns_frame(AAA=list(rng.normal(0.005, 0.05, 120)))
    funds = {"F": fund("F", "AAA"), "G": fund("G", "AAA")}
    out = simulate(funds, [("F", {"F": 1.0}), ("G", {"G": 1.0})], Plan(5000, 100, 5), paths=500, returns=r)
    assert out.scenarios[0].yearly == out.scenarios[1].yearly


def test_history_stats_describe_the_mix():
    r = returns_frame(AAA=[0.1, -0.5, 0.2] + [0.0] * 30)
    out = simulate({"F": fund("F", "AAA")}, [("F", {"F": 1.0})], Plan(1000, 0, 1), paths=10, returns=r)
    assert out.scenarios[0].history["max_drawdown_pct"] == -50.0
    assert out.window_start == "2010-01" and out.months == 33


def test_bad_requests_are_refused():
    r = returns_frame(AAA=[0.01] * 60)
    funds = {"F": fund("F", "AAA")}
    with pytest.raises(WhatIfError):
        simulate(funds, [("X", {"NOPE": 1.0})], Plan(1000, 0, 2), returns=r)
    with pytest.raises(WhatIfError):
        simulate(funds, [("F", {"F": 1.0})] * 4, Plan(1000, 0, 2), returns=r)


def test_blocks_wrap_around_the_history():
    idx = draw_months(10, 30, 4, np.random.default_rng(1), block=12)
    assert idx.shape == (4, 30) and idx.min() >= 0 and idx.max() <= 9
    assert ((idx[:, 1] - idx[:, 0]) % 10 == 1).all()
