"""The tradable universe (C1): thirty large US companies and the seventeen ETFs Atrium already profiles.

Everything here reads committed files, so prices, risk bands and analytics work without a market-data connection.
Refresh the files about once a month:  uv run python -m app.markets.refresh
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.models import Fund, FundConstituent
from app.seed.funds import HOUSE_FUNDS
from app.seed.history import load_etf_profiles, load_monthly_history
from app.services.fund_returns import monthly_returns
from app.services.xray import SECTOR_LABEL

SEED = Path(__file__).resolve().parent.parent / "seed"
DAILY_PATH = SEED / "market_daily.csv"
MONTHLY_PATH = SEED / "market_monthly.csv"
PROFILES_PATH = SEED / "market_profiles.json"
DAILY_START = date(2024, 10, 1)
CASH = "USD"
CASH_NAME = "Cash for trading"
STOCKS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V", "MA", "UNH", "JNJ", "LLY", "XOM",
          "CVX", "PG", "KO", "PEP", "WMT", "COST", "HD", "DIS", "NFLX", "AMD", "INTC", "BAC", "CRM", "ORCL", "NKE")
ETFS = ("SPY", "VOO", "VTI", "QQQ", "VUG", "VT", "VXUS", "VEA", "SCHD", "VYM", "XLK", "VGT", "BND", "AGG", "VCIT", "BIL",
        "SGOV")
# Yahoo Finance's sector names, mapped to the keys its ETF sector weights use.
SECTOR_KEYS = {"Technology": "technology", "Financial Services": "financial_services", "Healthcare": "healthcare",
               "Consumer Cyclical": "consumer_cyclical", "Consumer Defensive": "consumer_defensive",
               "Communication Services": "communication_services", "Industrials": "industrials", "Energy": "energy",
               "Utilities": "utilities", "Real Estate": "realestate", "Basic Materials": "basic_materials"}
VOLATILITY_MONTHS = 60
# Annualised volatility ceilings (%) for bands 1 to 4; anything above the last is band 5. They put Treasury bills in
# band 1, bond ETFs in 2, dividend ETFs in 3, the S&P 500 in 4 and most single stocks in 5, in line with the house funds.
BAND_LIMITS = (3.0, 9.0, 14.5, 22.0)


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    kind: str                   # stock | etf
    sector: str | None          # a key of SECTOR_LABEL, for stocks
    industry: str | None        # a stock's industry, or an ETF's category
    asset_class: str            # equity | bond | cash
    region: str                 # US | DM_ex_US | Global
    market_value: float | None  # market capitalisation for a stock, total assets for an ETF
    avg_volume: float | None    # shares traded on a typical day
    summary: str
    volatility_pct: float       # annualised, over the last five years of monthly returns
    risk_band: int

    @property
    def sector_label(self) -> str | None:
        return SECTOR_LABEL.get(self.sector, self.sector) if self.sector else None


def band_for_volatility(volatility_pct: float) -> int:
    return 1 + sum(volatility_pct > limit for limit in BAND_LIMITS)


@lru_cache(maxsize=1)
def load_market_profiles() -> dict:
    return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_market_daily() -> pd.DataFrame:
    return pd.read_csv(DAILY_PATH, index_col=0, parse_dates=True).sort_index()


@lru_cache(maxsize=1)
def load_market_monthly() -> pd.DataFrame:
    return pd.read_csv(MONTHLY_PATH, index_col=0, parse_dates=True).sort_index()


@lru_cache(maxsize=1)
def analytics_returns() -> pd.DataFrame:
    """Monthly returns of the house-fund ETFs, the benchmark and every stock, plus a flat line for cash."""
    prices = pd.concat([load_monthly_history(), load_market_monthly()], axis=1).sort_index()
    return monthly_returns(prices).assign(**{CASH: 0.0})


def _etf_classes() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for spec in HOUSE_FUNDS:
        for ticker, _weight, asset_class, region, _sector in spec["constituents"]:
            out[ticker] = (asset_class, region)
    return out


@lru_cache(maxsize=1)
def instruments() -> dict[str, Instrument]:
    profiles = load_market_profiles()["symbols"]
    classes = _etf_classes()
    returns = analytics_returns()
    out: dict[str, Instrument] = {}
    for symbol in (*STOCKS, *ETFS):
        p = profiles[symbol]
        recent = returns[symbol].dropna().iloc[-VOLATILITY_MONTHS:]
        volatility = round(float(recent.std(ddof=1)) * math.sqrt(12) * 100, 1)
        asset_class, region = classes.get(symbol, ("equity", "US"))
        stock = symbol in STOCKS
        out[symbol] = Instrument(
            symbol=symbol, name=p["name"], kind="stock" if stock else "etf",
            sector=p.get("sector") if stock else None,
            industry=p.get("industry") if stock else p.get("category"), asset_class=asset_class, region=region,
            market_value=p.get("market_cap") if stock else p.get("total_assets"), avg_volume=p.get("avg_volume"),
            summary=p.get("summary") or "", volatility_pct=volatility, risk_band=band_for_volatility(volatility))
    return out


def instrument(symbol: str) -> Instrument | None:
    return instruments().get(symbol.strip().upper())


def holding_objects() -> dict[str, Fund]:
    """Each tradable symbol, and cash, as a transient one-line fund, so the risk engine and the X-ray read a share held
    directly the same way they read a house fund. These objects are never added to a session."""
    out: dict[str, Fund] = {}
    for symbol, i in instruments().items():
        out[symbol] = Fund(code=symbol, name=i.name, category=i.kind, risk_band=i.risk_band, fee_bps=0,
                           min_investment=Decimal("0"), objective="", who_for="",
                           constituents=[FundConstituent(ticker=symbol, weight=Decimal("1"), asset_class=i.asset_class,
                                                         region=i.region, sector=i.sector or "broad")])
    out[CASH] = Fund(code=CASH, name=CASH_NAME, category="cash", risk_band=1, fee_bps=0, min_investment=Decimal("0"),
                     objective="", who_for="",
                     constituents=[FundConstituent(ticker=CASH, weight=Decimal("1"), asset_class="cash", region="US",
                                                   sector="cash")])
    return out


def xray_profiles() -> dict:
    """The ETF look-through profiles, plus one for each stock: the company itself, wholly in its sector."""
    out = dict(load_etf_profiles())
    for symbol, i in instruments().items():
        if i.kind == "stock":
            out[symbol] = {"expense_ratio": None, "top_holdings": [{"symbol": symbol, "name": i.name, "weight": 1.0}],
                           "sectors": {i.sector: 1.0} if i.sector else {}}
    return out
