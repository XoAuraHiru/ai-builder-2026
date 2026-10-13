"""Scenario Studio: replay real market history on what an investor holds, and apply explicit factor shocks.

The engine is deterministic. History replays compound the committed month-end returns of each holding over a window;
factor shocks act on each holding's look-through exposure (an equity ETF's sector weights, a bond or cash ETF's asset
class, a stock's sector). Gemini only proposes shocks; the arithmetic here is exact, the shocks are judgements.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

from app.markets.universe import CASH, analytics_returns, instruments, load_market_monthly
from app.models import Fund
from app.seed.history import load_etf_profiles, load_monthly_history
from app.services.fund_returns import constituent_weights, fund_returns
from app.services.portfolio import PortfolioView

WINDOWS = {"crisis_2008": ("2007-10", "2009-02", "The 2008 financial crisis"),
           "pandemic_2020": ("2020-01", "2020-03", "The 2020 pandemic crash"),
           "rates_2022": ("2021-12", "2022-12", "The 2022 rate shock")}
WINDOW_NOTES = {"pandemic_2020": ("Month-end closes: the intramonth low of late March 2020 is not captured, so the "
                                  "real fall was deeper than shown.",)}
FACTORS = ("us_equity", "intl_equity", "bonds", "cash")  # asset-class factors
SECTORS = ("technology", "communication_services", "consumer_cyclical", "consumer_defensive", "energy",
           "financial_services", "healthcare", "industrials", "basic_materials", "realestate", "utilities")
EQUITY_BOUNDS = (-70.0, 50.0)
BOUNDS: dict[str, tuple[float, float]] = {"us_equity": EQUITY_BOUNDS, "intl_equity": EQUITY_BOUNDS,
                                          "bonds": (-30.0, 20.0), "cash": (-5.0, 5.0),
                                          **{sector: EQUITY_BOUNDS for sector in SECTORS}}
INTERNATIONAL_ETFS = frozenset({"VT", "VXUS", "VEA"})
INTERNATIONAL_REGIONS = frozenset({"DM_ex_US", "Global", "EM"})


# --- data ---------------------------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _prices() -> pd.DataFrame:
    return pd.concat([load_monthly_history(), load_market_monthly()], axis=1).sort_index()


def _month(key: str) -> pd.Timestamp:
    return pd.Timestamp(f"{key}-01")


def _first_price(ticker: str) -> pd.Timestamp | None:
    return _prices()[ticker].first_valid_index() if ticker in _prices() else None


def _region_factor(ticker: str, region: str) -> str:
    return "intl_equity" if ticker in INTERNATIONAL_ETFS or region in INTERNATIONAL_REGIONS else "us_equity"


def _is_house_fund(code: str) -> bool:
    return code != CASH and code not in instruments()


def is_empty(view: PortfolioView) -> bool:
    """Nothing to stress-test: no holding other than paper cash is worth anything."""
    return not any(h.instrument != CASH and h.value > 0 for h in view.holdings)


def _held(view: PortfolioView) -> list[tuple[str, str, float]]:
    return [(h.instrument, h.name, float(h.value)) for h in view.holdings if h.value > 0]


# --- exposures and shocks -----------------------------------------------------------------------------------------

@dataclass
class Exposure:
    symbol: str
    name: str
    value_usd: float
    slices: list[dict]  # [{factor, fallback, weight}]; weights sum to 1 per holding


@dataclass
class Impact:
    total_usd: float
    total_pct: float
    holdings: list[dict] = field(default_factory=list)   # [{symbol, name, value_usd, change_pct, change_usd}]
    by_factor: list[dict] = field(default_factory=list)  # [{factor, change_usd}]


def _slices(fund: Fund) -> list[dict]:
    """A holding's look-through: each slice is shocked by its factor, or by its fallback when its factor has none."""
    profiles = load_etf_profiles()
    out: dict[tuple[str, str | None], float] = {}

    def add(factor: str, fallback: str | None, weight: float) -> None:
        out[(factor, fallback)] = out.get((factor, fallback), 0.0) + weight

    total = sum(float(c.weight) for c in fund.constituents) or 1.0
    for c in fund.constituents:
        weight = float(c.weight) / total
        inst = instruments().get(c.ticker)
        if c.ticker == CASH or c.asset_class == "cash":
            add("cash", None, weight)
        elif c.asset_class == "bond":
            add("bonds", None, weight)
        elif inst is not None and inst.kind == "stock":
            region = _region_factor(c.ticker, c.region)
            if inst.sector in SECTORS:
                add(inst.sector, region, weight)
            else:
                add(region, None, weight)
        else:
            region = _region_factor(c.ticker, c.region)
            sectors = {k: float(v) for k, v in (profiles.get(c.ticker, {}).get("sectors") or {}).items()
                       if k in SECTORS and v > 0}
            sector_total = sum(sectors.values())
            if not sector_total:
                add(region, None, weight)
            for sector, share in sectors.items():
                add(sector, region, weight * share / sector_total)
    return [{"factor": f, "fallback": fb, "weight": w} for (f, fb), w in out.items()]


def exposures(view: PortfolioView, funds: dict[str, Fund]) -> list[Exposure]:
    return [Exposure(code, name, value, _slices(funds[code])) for code, name, value in _held(view)]


def _effective(slice_: dict, shocks: dict[str, float]) -> tuple[str, float]:
    factor, fallback = slice_["factor"], slice_["fallback"]
    if factor in shocks or fallback is None:
        return factor, float(shocks.get(factor, 0.0))
    return fallback, float(shocks.get(fallback, 0.0))


def apply_shocks(view: PortfolioView, funds: dict[str, Fund], shocks: dict[str, float]) -> Impact:
    """Shocks are percentages, already validated against BOUNDS."""
    rows, by_factor, total_change = [], {}, 0.0
    held = exposures(view, funds)
    total_value = sum(e.value_usd for e in held)
    for e in held:
        pct = 0.0
        for s in e.slices:
            factor, shock = _effective(s, shocks)
            pct += s["weight"] * shock
            by_factor[factor] = by_factor.get(factor, 0.0) + e.value_usd * s["weight"] * shock / 100
        change = e.value_usd * pct / 100
        total_change += change
        rows.append({"symbol": e.symbol, "name": e.name, "value_usd": round(e.value_usd, 2),
                     "change_pct": round(pct, 2), "change_usd": round(change, 2)})
    factors = sorted(({"factor": f, "change_usd": round(v, 2)} for f, v in by_factor.items()),
                     key=lambda f: f["change_usd"])
    return Impact(total_usd=round(total_change, 2),
                  total_pct=round(total_change / total_value * 100, 2) if total_value else 0.0,
                  holdings=rows, by_factor=factors)


# --- history replays ----------------------------------------------------------------------------------------------

@dataclass
class Replay:
    key: str
    title: str
    start: str
    end: str
    loss_usd: float               # the window's change in value: negative is a loss
    loss_pct: float
    trough_month: str | None      # None when the portfolio never fell below its starting value
    recovery_months: int | None   # months from the trough back to the start; None when not within the data
    worst_holding: dict | None    # {symbol, name, pct}; None when only cash is held
    holdings: list[dict] = field(default_factory=list)  # [{symbol, name, value_usd, change_pct, change_usd}]
    notes: list[str] = field(default_factory=list)


def _stand_in(code: str) -> str:
    inst = instruments()[code]
    if inst.kind == "stock":
        return "XLK" if inst.sector == "technology" else "SPY"
    if inst.asset_class == "bond":
        return "BND"
    if inst.asset_class == "cash":
        return "BIL"
    return "VEA" if inst.region == "DM_ex_US" else "SPY"


def _holding_returns(code: str, fund: Fund, start: pd.Timestamp, months: pd.DatetimeIndex,
                     window: pd.DatetimeIndex) -> tuple[pd.Series, list[str]]:
    """Monthly returns of one holding over the replay's months, and the notes that explain any stand-in."""
    returns = analytics_returns()
    if code == CASH:
        return pd.Series(0.0, index=months), []
    if not _is_house_fund(code):
        series = returns[code].reindex(months)
        if series.reindex(window).notna().all():
            return series.fillna(0.0), []
        proxy = _stand_in(code)
        verb = "listed" if instruments()[code].kind == "stock" else "launched"
        return returns[proxy].reindex(months).fillna(0.0), [f"{code} had not {verb} yet; {proxy} stands in."]
    notes = []
    for c in sorted(fund.constituents, key=lambda c: c.ticker):
        first = _first_price(c.ticker)
        if first is None or first > start:
            since = f"until {first:%B %Y}" if first is not None else "in this window"
            notes.append(f"{fund.name}: {c.ticker} had no prices {since}; until then its {float(c.weight):.0%} weight "
                         "is spread across the fund's other ETFs.")
    return fund_returns(constituent_weights(fund), returns).reindex(months).fillna(0.0), notes


def trough_and_recovery(path: pd.Series, end: str) -> tuple[str | None, int | None]:
    """The window's lowest month, and the months from it until the value is back to 1.0 (its start)."""
    window = path.loc[:_month(end)]
    if window.empty or window.min() >= 1.0:
        return None, 0
    trough = window.idxmin()
    after = path.loc[trough:]
    back = after[after >= 1.0]
    if back.empty:
        return f"{trough:%Y-%m}", None
    regained = back.index[0]
    return f"{trough:%Y-%m}", (regained.year - trough.year) * 12 + regained.month - trough.month


def _replay(key: str, held: list[tuple[str, str, float]], funds: dict[str, Fund]) -> Replay:
    start_key, end_key, title = WINDOWS[key]
    start, end = _month(start_key), _month(end_key)
    index = analytics_returns().index
    months = index[index > start]
    window = months[months <= end]
    notes = list(WINDOW_NOTES.get(key, ()))
    rows, path, total_value, total_change = [], pd.Series(0.0, index=months), 0.0, 0.0
    for code, name, value in held:
        returns, why = _holding_returns(code, funds[code], start, months, window)
        notes.extend(n for n in why if n not in notes)
        growth = (1 + returns).cumprod()
        change_pct = (float(growth.loc[end]) - 1) * 100
        change = value * change_pct / 100
        rows.append({"symbol": code, "name": name, "value_usd": round(value, 2), "change_pct": round(change_pct, 2),
                     "change_usd": round(change, 2)})
        path += value * growth
        total_value += value
        total_change += change
    if not total_value:
        return Replay(key, title, start_key, end_key, 0.0, 0.0, None, 0, None, rows, notes)
    trough, recovery = trough_and_recovery(path / total_value, end_key)
    invested = [r for r in rows if r["symbol"] != CASH]
    worst = min(invested, key=lambda r: r["change_pct"]) if invested else None
    return Replay(key, title, start_key, end_key, round(total_change, 2), round(total_change / total_value * 100, 2),
                  trough, recovery,
                  {"symbol": worst["symbol"], "name": worst["name"], "pct": worst["change_pct"]} if worst else None,
                  rows, notes)


def replays(view: PortfolioView, funds: dict[str, Fund]) -> list[Replay]:
    held = _held(view)
    return [_replay(key, held, funds) for key in WINDOWS]


# --- the proposal Gemini returns, and its validation ---------------------------------------------------------------

DEFAULT_REFUSAL = ("Scenario Studio models market scenarios, such as a rate rise, an oil shock or a sector sell-off. "
                   "It cannot help with this request.")


class Shock(BaseModel):
    factor: str  # one of FACTORS or SECTORS
    pct: float
    reason: str = Field(max_length=200)


class ScenarioProposal(BaseModel):
    in_scope: bool
    refusal: str = Field(default="", max_length=300)  # when not in scope
    title: str = Field(default="", max_length=120)
    horizon_months: int = Field(default=12, ge=1, le=60)
    shocks: list[Shock] = Field(default_factory=list, max_length=16)
    analogue: Literal["crisis_2008", "pandemic_2020", "rates_2022", "none"] = "none"
    analogue_reason: str = Field(default="", max_length=300)
    assumptions: list[str] = Field(default_factory=list, max_length=6)


@dataclass
class Validated:
    shocks: dict[str, float]  # every asset-class factor (0 when not given) and each sector given
    clamped: list[str]        # factors held to their bounds
    dropped: list[str]        # factors not in FACTORS or SECTORS, repeats and non-numbers, as Gemini wrote them
    proposal: ScenarioProposal  # with only the kept shocks, at their clamped values


def clamp(factor: str, pct: float) -> tuple[float, bool]:
    low, high = BOUNDS[factor]
    held = min(max(pct, low), high)
    return held, held != pct


def normalise_factor(factor: str) -> str:
    return factor.strip().lower().replace(" ", "_").replace("-", "_")


def validate_proposal(p: ScenarioProposal) -> Validated:
    """Keep known factors once each, hold every shock within its bounds, and say what was changed."""
    if not p.in_scope:
        refused = p.model_copy(update={"shocks": [], "refusal": p.refusal.strip() or DEFAULT_REFUSAL})
        return Validated({}, [], [], refused)
    shocks: dict[str, float] = {}
    kept: list[Shock] = []
    clamped: list[str] = []
    dropped: list[str] = []
    for s in p.shocks:
        factor = normalise_factor(s.factor)
        if factor not in BOUNDS or factor in shocks or not math.isfinite(s.pct):
            dropped.append(s.factor)
            continue
        pct, was_clamped = clamp(factor, s.pct)
        if was_clamped:
            clamped.append(factor)
        shocks[factor] = pct
        kept.append(Shock(factor=factor, pct=pct, reason=s.reason))
    for factor in FACTORS:
        shocks.setdefault(factor, 0.0)
    return Validated(shocks, clamped, dropped, p.model_copy(update={"shocks": kept}))
