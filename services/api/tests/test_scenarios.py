"""Scenario Studio: the deterministic engine (history replays, factor shocks), the bounded proposal and its suites.

Every expected value is worked out here from the committed prices and ETF profiles, never by calling the engine."""
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from app.markets.universe import holding_objects, instruments
from app.seed.funds import house_fund_objects
from app.seed.history import load_etf_profiles
from app.services.portfolio import HoldingView, PortfolioView
from app.services.scenarios import (WINDOWS, apply_shocks, exposures, is_empty, replays, trough_and_recovery)

SEED = Path(__file__).resolve().parents[1] / "app" / "seed"
FUNDS = {**holding_objects(), **house_fund_objects()}


def prices() -> pd.DataFrame:
    """The committed month-end closes, read straight from the files."""
    history = pd.read_csv(SEED / "history_monthly.csv", index_col=0, parse_dates=True)
    market = pd.read_csv(SEED / "market_monthly.csv", index_col=0, parse_dates=True)
    return pd.concat([history, market], axis=1).sort_index()


def ratio_pct(ticker: str, start: str, end: str) -> float:
    p = prices()
    return (p.loc[f"{end}-01", ticker] / p.loc[f"{start}-01", ticker] - 1) * 100


def make_view(values: dict[str, float]) -> PortfolioView:
    holdings, total = [], Decimal("0")
    for code, value in values.items():
        amount = Decimal(str(value))
        if code == "USD":
            kind, name = "cash", "Cash for trading"
        elif code in FUNDS and code.startswith("ATR-"):
            kind, name = "fund", FUNDS[code].name
        else:
            kind, name = instruments()[code].kind, instruments()[code].name
        holdings.append(HoldingView(instrument=code, name=name, units=amount, price=Decimal("1"),
                                    price_as_of=date(2026, 10, 1), value=amount, cost_basis=amount, pnl=Decimal("0"),
                                    pnl_pct=Decimal("0"), kind=kind))
        total += amount
    return PortfolioView(account_id="acc-1", as_of=date(2026, 10, 1), total_value=total, total_cost=total,
                         holdings=holdings, by_instrument={h.instrument: h.value for h in holdings})


def by_symbol(rows: list[dict]) -> dict[str, dict]:
    return {r["symbol"]: r for r in rows}


# --- factor shocks -------------------------------------------------------------------------------------------------

def test_shocks_apply_through_the_look_through_to_every_holding():
    view = make_view({"ATR-BAL": 10000, "NVDA": 5000, "USD": 1000})
    impact = apply_shocks(view, FUNDS, {"us_equity": -10, "bonds": -5, "technology": -40, "cash": 0})
    rows = by_symbol(impact.holdings)

    assert rows["NVDA"]["change_pct"] == -40.0 and rows["NVDA"]["change_usd"] == -2000.0

    vti = load_etf_profiles()["VTI"]["sectors"]
    total = sum(vti.values())
    vti_pct = sum(w / total * (-40 if sector == "technology" else -10) for sector, w in vti.items())
    bal_pct = 0.6 * vti_pct + 0.4 * -5
    assert rows["ATR-BAL"]["change_pct"] == pytest.approx(bal_pct, abs=0.01)
    assert rows["ATR-BAL"]["change_usd"] == pytest.approx(10000 * bal_pct / 100, abs=0.01)

    assert rows["USD"]["change_usd"] == 0 and rows["USD"]["change_pct"] == 0
    expected_total = -2000 + 10000 * bal_pct / 100
    assert impact.total_usd == pytest.approx(expected_total, abs=0.01)
    assert impact.total_usd == pytest.approx(sum(r["change_usd"] for r in impact.holdings), abs=0.01)
    assert impact.total_pct == pytest.approx(expected_total / 16000 * 100, abs=0.01)

    factors = {f["factor"]: f["change_usd"] for f in impact.by_factor}
    assert factors["bonds"] == pytest.approx(10000 * 0.4 * -5 / 100, abs=0.01)
    assert factors["technology"] == pytest.approx(-2000 + 10000 * 0.6 * vti["technology"] / total * -40 / 100,
                                                  abs=0.01)


def test_international_funds_fall_back_to_the_international_shock():
    view = make_view({"ATR-GLB": 1000, "ATR-GRW": 1000})
    impact = apply_shocks(view, FUNDS, {"intl_equity": -20, "us_equity": 0, "bonds": 0, "cash": 0})
    rows = by_symbol(impact.holdings)
    assert rows["ATR-GLB"]["change_usd"] == pytest.approx(-200, abs=0.01)  # VT, VXUS and VEA all count as international
    assert rows["ATR-GRW"]["change_usd"] == 0


def test_every_holdings_exposure_adds_up_to_one():
    view = make_view({"ATR-BAL": 10000, "ATR-GLB": 3000, "ATR-CASH": 500, "NVDA": 5000, "BND": 800, "USD": 1000})
    out = {e.symbol: e for e in exposures(view, FUNDS)}
    for e in out.values():
        assert sum(s["weight"] for s in e.slices) == pytest.approx(1, abs=1e-9), e.symbol
    assert out["NVDA"].slices == [{"factor": "technology", "fallback": "us_equity", "weight": 1.0}]
    assert out["USD"].slices == [{"factor": "cash", "fallback": None, "weight": 1.0}]
    assert out["BND"].slices == [{"factor": "bonds", "fallback": None, "weight": 1.0}]
    assert {s["factor"] for s in out["ATR-CASH"].slices} == {"cash"}
    bonds = [s for s in out["ATR-BAL"].slices if s["factor"] == "bonds"]
    assert bonds == [{"factor": "bonds", "fallback": None, "weight": pytest.approx(0.4)}]
    assert {s["fallback"] for s in out["ATR-GLB"].slices} == {"intl_equity"}


# --- history replays -----------------------------------------------------------------------------------------------

def test_replays_use_month_end_closes_over_each_window():
    view = make_view({"ATR-BAL": 10000, "NVDA": 5000, "USD": 1000, "META": 2000})
    out = {r.key: r for r in replays(view, FUNDS)}
    assert list(out) == ["crisis_2008", "pandemic_2020", "rates_2022"] == list(WINDOWS)

    crisis = out["crisis_2008"]
    assert (crisis.start, crisis.end) == ("2007-10", "2009-02")
    rows = by_symbol(crisis.holdings)

    p = prices().loc["2007-10-01":"2009-02-01"]
    r = (p / p.shift(1) - 1).iloc[1:]
    bal_pct = ((1 + 0.6 * r["VTI"] + 0.4 * r["BND"]).prod() - 1) * 100  # ATR-BAL, rebalanced monthly
    assert rows["ATR-BAL"]["change_pct"] == pytest.approx(bal_pct, abs=0.01)
    assert rows["ATR-BAL"]["change_usd"] == pytest.approx(10000 * bal_pct / 100, abs=0.01)

    nvda_pct = ratio_pct("NVDA", "2007-10", "2009-02")
    assert rows["NVDA"]["change_pct"] == pytest.approx(nvda_pct, abs=0.01)

    spy_pct = ratio_pct("SPY", "2007-10", "2009-02")  # META had not listed: the S&P 500 stands in
    assert rows["META"]["change_pct"] == pytest.approx(spy_pct, abs=0.01)
    assert any("META" in n and "SPY" in n for n in crisis.notes)
    assert rows["USD"]["change_usd"] == 0

    expected_usd = 10000 * bal_pct / 100 + 5000 * nvda_pct / 100 + 2000 * spy_pct / 100
    assert crisis.loss_usd == pytest.approx(expected_usd, abs=0.02)
    assert crisis.loss_pct == pytest.approx(expected_usd / 18000 * 100, abs=0.01)
    assert crisis.worst_holding["symbol"] == "NVDA"
    assert crisis.worst_holding["pct"] == pytest.approx(nvda_pct, abs=0.01)

    # META has traded since 2012, so the later windows use its own prices and say nothing about it.
    assert by_symbol(out["rates_2022"].holdings)["META"]["change_pct"] == pytest.approx(
        ratio_pct("META", "2021-12", "2022-12"), abs=0.01)
    assert not any("META" in n for n in out["rates_2022"].notes)
    assert any("intramonth" in n for n in out["pandemic_2020"].notes)


def test_a_tech_stock_that_had_not_listed_uses_the_tech_etf():
    out = {r.key: r for r in replays(make_view({"AVGO": 1000}), FUNDS)}
    assert out["crisis_2008"].holdings[0]["change_pct"] == pytest.approx(ratio_pct("XLK", "2007-10", "2009-02"),
                                                                         abs=0.01)
    assert any("AVGO" in n and "XLK" in n for n in out["crisis_2008"].notes)


def test_a_house_fund_says_when_its_etfs_are_backfilled_within_the_window():
    crisis, pandemic, rates = replays(make_view({"ATR-GLB": 1000}), FUNDS)
    named = {t for n in crisis.notes for t in re.findall(r"\b(VT|VXUS|VEA)\b", n)}
    assert named == {"VT", "VXUS"}  # VEA traded from July 2007; the other two had not started
    assert not any(re.search(r"\bVT\b|VXUS", n) for n in rates.notes)


def test_recovery_counts_months_from_the_trough_back_to_the_start():
    path = pd.Series([0.95, 0.80, 0.90, 0.99, 1.02, 1.10],
                     index=pd.to_datetime(["2020-02-01", "2020-03-01", "2020-04-01", "2020-05-01", "2020-06-01",
                                           "2020-07-01"]))
    assert trough_and_recovery(path, "2020-03") == ("2020-03", 3)
    never = pd.Series([0.9, 0.7, 0.8], index=pd.to_datetime(["2020-02-01", "2020-03-01", "2020-04-01"]))
    assert trough_and_recovery(never, "2020-03") == ("2020-03", None)
    flat = pd.Series([1.0, 1.0], index=pd.to_datetime(["2020-02-01", "2020-03-01"]))
    assert trough_and_recovery(flat, "2020-03") == (None, 0)


def test_a_replays_recovery_follows_the_portfolio_after_the_window():
    pandemic = {r.key: r for r in replays(make_view({"SPY": 1000}), FUNDS)}["pandemic_2020"]
    spy = prices()["SPY"]
    path = spy.loc["2020-02-01":] / spy.loc["2020-01-01"]
    trough = path.loc[:"2020-03-01"].idxmin()
    back = path.loc[trough:][path.loc[trough:] >= 1].index[0]
    months = (back.year - trough.year) * 12 + back.month - trough.month
    assert pandemic.trough_month == f"{trough:%Y-%m}" and pandemic.recovery_months == months


def test_cash_alone_has_nothing_to_stress_test():
    view = make_view({"USD": 1000})
    assert is_empty(view) and is_empty(make_view({}))
    assert not is_empty(make_view({"USD": 1000, "ATR-CASH": 10}))
    for replay in replays(view, FUNDS):
        assert replay.loss_usd == 0 and replay.loss_pct == 0
        assert replay.worst_holding is None and replay.recovery_months == 0
    impact = apply_shocks(view, FUNDS, {"us_equity": -50, "bonds": -20, "cash": 0, "intl_equity": -50})
    assert impact.total_usd == 0 and impact.total_pct == 0
    nothing = apply_shocks(make_view({}), FUNDS, {"us_equity": -50})
    assert nothing.total_usd == 0 and nothing.holdings == []
    assert all(r.loss_usd == 0 and r.holdings == [] for r in replays(make_view({}), FUNDS))
