from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from app.models import Fund, FundConstituent
from app.services.analyzer import (MIN_SHARE_MONTHS, AnalysisRequest, AnalyzerError, analyze, share_options)
from app.services.whatif import Plan, simulate


def fund(code="F", ticker="AAA", fee_bps=0, minimum="1000"):
    return Fund(code=code, name=f"Fund {code}", category="balanced", risk_band=3, fee_bps=fee_bps,
                min_investment=Decimal(minimum), objective="", who_for="", inception_on=date(2024, 10, 1),
                constituents=[FundConstituent(ticker=ticker, weight=Decimal("1"), asset_class="equity", region="US",
                                              sector="broad")])


def returns_frame(**sequences):
    n = len(next(iter(sequences.values())))
    idx = pd.date_range("2010-01-01", periods=n, freq="MS")
    return pd.DataFrame(sequences, index=idx, dtype="float64")


FUNDS = {"F": fund()}
FUND_RETURNS = returns_frame(AAA=[0.01] * 60)


def trust(**kw):
    return AnalysisRequest(**{"kind": "unit_trust", "code": "F", "initial_usd": 1000, "monthly_usd": 0, "years": 2,
                              **kw})


def share(**kw):
    return AnalysisRequest(**{"kind": "share", "code": "AAA", "initial_usd": 1000, "monthly_usd": 0, "years": 2, **kw})


def run(req, share_returns=None):
    return analyze(FUNDS, req, paths=100, fund_returns_df=FUND_RETURNS, share_returns_df=share_returns)


def shares_frame(months=MIN_SHARE_MONTHS, aaa=0.01, spy=0.005):
    return returns_frame(AAA=[aaa] * months, SPY=[spy] * months)


def test_one_time_amount_is_required():
    with pytest.raises(AnalyzerError, match="one-time amount"):
        run(trust(initial_usd=0, monthly_usd=100))


def test_unit_trust_minimum_is_enforced():
    with pytest.raises(AnalyzerError, match="Fund F needs at least \\$1,000 to start"):
        run(trust(initial_usd=999))


def test_unit_trust_monthly_below_50_is_refused():
    with pytest.raises(AnalyzerError, match="Monthly amounts start at \\$50"):
        run(trust(monthly_usd=49))


def test_unit_trust_monthly_of_50_is_accepted():
    out = run(trust(monthly_usd=50))
    assert out.result.contributed == 1000 + 50 * 24


def test_share_monthly_amount_is_refused():
    with pytest.raises(AnalyzerError, match="unit trusts only"):
        run(share(monthly_usd=100), shares_frame())


def test_unknown_fund_and_symbol_are_refused():
    with pytest.raises(AnalyzerError, match="Choose one of Atrium's funds"):
        run(trust(code="NOPE"))
    with pytest.raises(AnalyzerError, match="ZZZ is not one of the shares"):
        run(share(code="ZZZ"), shares_frame())


def test_short_share_history_is_refused():
    with pytest.raises(AnalyzerError, match="too little history"):
        run(share(), shares_frame(months=MIN_SHARE_MONTHS - 1))
    assert run(share(), shares_frame()).result.months == MIN_SHARE_MONTHS


def test_years_must_be_1_to_40():
    for years in (0, 41):
        with pytest.raises(AnalyzerError, match="1 to 40 years"):
            run(trust(years=years))


def test_share_is_fee_free_and_compared_with_spy():
    out = run(share(), shares_frame())
    assert out.fee_bps == 0 and out.result.scenarios[0].fee_cost == 0
    assert out.result.scenarios[0].final["p50"] == round(1000 * 1.01 ** 24, 2)
    assert out.comparison is not None and out.comparison.label == "S&P 500 (SPY)"
    assert out.comparison.final["p50"] == round(1000 * 1.005 ** 24, 2)


def test_share_and_spy_share_the_same_draws():
    series = [0.05, -0.04, 0.02, -0.01, 0.03, -0.06] * (MIN_SHARE_MONTHS // 6)
    out = run(share(years=5), returns_frame(AAA=series, SPY=series))
    assert out.result.scenarios[0].final == out.comparison.final


def test_unit_trust_matches_the_what_if_engine():
    funds = {"F": fund(fee_bps=50)}
    r = returns_frame(AAA=[0.02, -0.01, 0.015, 0.0] * 15)
    out = analyze(funds, trust(monthly_usd=100, years=3), paths=200, fund_returns_df=r)
    direct = simulate(funds, [("Fund F", {"F": 1.0})], Plan(1000.0, 100.0, 3), paths=200, returns=r)
    assert out.result.scenarios[0].final == direct.scenarios[0].final
    assert out.comparison is None and out.name == "Fund F" and out.fee_bps == 50


def test_share_options_lists_only_symbols_with_ten_years():
    options = share_options(returns_frame(AAA=[0.01] * MIN_SHARE_MONTHS, BBB=[None] + [0.01] * (MIN_SHARE_MONTHS - 1)),
                            names={"AAA": ("Alpha Corp", "stock"), "BBB": ("Beta ETF", "etf")})
    assert [o["symbol"] for o in options] == ["AAA"]
    assert options[0] == {"symbol": "AAA", "name": "Alpha Corp", "kind": "stock", "history_start": "2010-01"}


def test_real_data_offers_every_stock_and_most_etfs():
    symbols = {o["symbol"] for o in share_options()}
    assert {"NVDA", "META", "TSLA", "SPY", "QQQ"} <= symbols
    assert "SGOV" not in symbols  # launched 2020: under ten years of history
