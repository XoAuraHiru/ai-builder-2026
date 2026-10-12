"""Portfolio X-ray (B3): look through house funds to the ETFs, sectors, regions and companies underneath.

Company exposure comes from each ETF's ten largest holdings, so it is a lower bound; coverage_pct says how much of the
stock exposure those holdings explain. Warnings are fixed rules with their thresholds in this file.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from app.models import Fund

SECTOR_LABEL = {
    "technology": "Technology", "financial_services": "Financials", "healthcare": "Health care",
    "consumer_cyclical": "Consumer discretionary", "consumer_defensive": "Consumer staples",
    "communication_services": "Communication", "industrials": "Industrials", "energy": "Energy",
    "utilities": "Utilities", "realestate": "Real estate", "basic_materials": "Materials",
}
REGION_LABEL = {"US": "United States", "DM_ex_US": "Developed markets outside the US", "EM": "Emerging markets",
                "Global": "Global (US and international)"}
ASSET_LABEL = {"equity": "Stocks", "bond": "Bonds", "cash": "Cash and T-bills"}
NON_EQUITY = {"bond": "Bonds", "cash": "Cash and T-bills"}
COMPANY_LIMIT_PCT = 5.0
SECTOR_LIMIT_PCT = 35.0
FUND_LIMIT_PCT = 60.0
HOME_LIMIT_PCT = 90.0
OVERLAP_ETF_PCT = 25.0
OVERLAP_COMPANY_PCT = 15.0


@dataclass
class Exposure:
    name: str
    value_usd: float
    pct: float


@dataclass
class EtfExposure:
    ticker: str
    asset_class: str
    value_usd: float
    pct: float
    expense_ratio_pct: float | None


@dataclass
class Company:
    symbol: str
    name: str
    value_usd: float
    pct: float
    via: list[str]


@dataclass
class Overlap:
    funds: list[str]
    names: list[str]
    shared_etfs_pct: float
    shared_companies_pct: float
    top_shared: list[str]


@dataclass
class Fees:
    atrium_annual_usd: float
    etf_annual_usd: float
    total_annual_usd: float
    total_pct: float
    ten_year_usd: float


@dataclass
class XRayWarning:
    code: str
    severity: str  # caution | info
    title: str
    message: str


@dataclass
class XRay:
    total_value_usd: float
    etfs: list[EtfExposure]
    sectors: list[Exposure]
    regions: list[Exposure]
    asset_classes: list[Exposure]
    companies: list[Company]
    coverage_pct: float
    overlaps: list[Overlap]
    fees: Fees
    warnings: list[XRayWarning]
    profiles_as_of: str


def join_words(items: list[str]) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""


def overlap_words(o: Overlap) -> str:
    """Only the overlaps that exist: "20.1% in the same companies", not "0.0% in the same ETFs and ..."."""
    parts = []
    if o.shared_etfs_pct > 0:
        parts.append(f"{o.shared_etfs_pct:.1f}% in the same ETFs")
    if o.shared_companies_pct > 0:
        parts.append(f"{o.shared_companies_pct:.1f}% in the same companies")
    return join_words(parts) or "no shared holdings"


def _ranked(values: dict[str, float], total: float, labels: dict[str, str] | None = None) -> list[Exposure]:
    rows = [Exposure(name=(labels or {}).get(k, k), value_usd=round(v, 2), pct=round(v / total * 100, 1))
            for k, v in values.items() if v > 0.005]
    return sorted(rows, key=lambda e: -e.value_usd)


def fund_company_weights(fund: Fund, profiles: dict) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for c in fund.constituents:
        if c.asset_class != "equity":
            continue
        for h in profiles.get(c.ticker, {}).get("top_holdings", []):
            out[h["symbol"]] += float(c.weight) * h["weight"]
    return out


def xray(holdings: dict[str, float], funds: dict[str, Fund], profiles: dict, profiles_as_of: str = "") -> XRay:
    total = sum(holdings.values())
    etf_value: dict[str, float] = defaultdict(float)
    etf_class: dict[str, str] = {}
    region: dict[str, float] = defaultdict(float)
    asset: dict[str, float] = defaultdict(float)
    for code, value in holdings.items():
        for c in funds[code].constituents:
            v = value * float(c.weight)
            etf_value[c.ticker] += v
            etf_class[c.ticker] = c.asset_class
            region[c.region] += v
            asset[c.asset_class] += v

    sectors: dict[str, float] = defaultdict(float)
    companies: dict[str, dict] = {}
    equity = covered = 0.0
    for ticker, v in etf_value.items():
        if etf_class[ticker] in NON_EQUITY:
            sectors[NON_EQUITY[etf_class[ticker]]] += v
            continue
        equity += v
        profile = profiles.get(ticker, {})
        weights = profile.get("sectors") or {}
        weight_total = sum(weights.values())
        if weight_total > 0:
            for key, w in weights.items():
                sectors[SECTOR_LABEL.get(key, key.replace("_", " ").capitalize())] += v * w / weight_total
        else:
            sectors["Other stocks"] += v
        for h in profile.get("top_holdings", []):
            entry = companies.setdefault(h["symbol"], {"name": h["name"], "value": 0.0, "via": set()})
            entry["value"] += v * h["weight"]
            entry["via"].add(ticker)
            covered += v * h["weight"]

    company_rows = sorted((Company(symbol=s, name=e["name"], value_usd=round(e["value"], 2),
                                   pct=round(e["value"] / total * 100, 2), via=sorted(e["via"]))
                           for s, e in companies.items()), key=lambda c: -c.value_usd)[:10]
    etf_rows = sorted((EtfExposure(ticker=t, asset_class=etf_class[t], value_usd=round(v, 2),
                                   pct=round(v / total * 100, 1),
                                   expense_ratio_pct=(None if profiles.get(t, {}).get("expense_ratio") is None
                                                      else round(profiles[t]["expense_ratio"] * 100, 2)))
                       for t, v in etf_value.items()), key=lambda e: -e.value_usd)

    overlaps: list[Overlap] = []
    for a, b in combinations(sorted(holdings), 2):
        wa = {c.ticker: float(c.weight) for c in funds[a].constituents}
        wb = {c.ticker: float(c.weight) for c in funds[b].constituents}
        shared_etfs = sum(min(wa[t], wb[t]) for t in wa.keys() & wb.keys())
        ca, cb = fund_company_weights(funds[a], profiles), fund_company_weights(funds[b], profiles)
        shared = {s: min(ca[s], cb[s]) for s in ca.keys() & cb.keys()}
        shared_companies = sum(shared.values())
        if shared_etfs >= 0.10 or shared_companies >= 0.05:
            top = [companies[s]["name"] if s in companies else s
                   for s, _ in sorted(shared.items(), key=lambda kv: -kv[1])[:3]]
            overlaps.append(Overlap(funds=[a, b], names=[funds[a].name, funds[b].name],
                                    shared_etfs_pct=round(shared_etfs * 100, 1),
                                    shared_companies_pct=round(shared_companies * 100, 1), top_shared=top))

    atrium_fee = sum(v * funds[c].fee_bps / 10_000 for c, v in holdings.items())
    etf_fee = sum(v * (profiles.get(t, {}).get("expense_ratio") or 0.0) for t, v in etf_value.items())
    fees = Fees(atrium_annual_usd=round(atrium_fee, 2), etf_annual_usd=round(etf_fee, 2),
                total_annual_usd=round(atrium_fee + etf_fee, 2),
                total_pct=round((atrium_fee + etf_fee) / total * 100, 2), ten_year_usd=round((atrium_fee + etf_fee) * 10, 2))
    sector_rows = _ranked(sectors, total)
    return XRay(total_value_usd=round(total, 2), etfs=etf_rows, sectors=sector_rows,
                regions=_ranked(region, total, REGION_LABEL), asset_classes=_ranked(asset, total, ASSET_LABEL),
                companies=company_rows, coverage_pct=round(covered / equity * 100, 1) if equity else 0.0,
                overlaps=overlaps, fees=fees,
                warnings=_warnings(holdings, funds, total, company_rows, sector_rows, region, overlaps),
                profiles_as_of=profiles_as_of)


def _warnings(holdings, funds, total, companies, sectors, region, overlaps) -> list[XRayWarning]:
    out: list[XRayWarning] = []
    for c in companies:
        if c.pct > COMPANY_LIMIT_PCT:
            out.append(XRayWarning("CONC_COMPANY", "caution", "One company is a large share",
                                   f"{c.name} is {c.pct:.1f}% of your portfolio, held through {join_words(c.via)}."))
    for s in sectors:
        if s.name not in NON_EQUITY.values() and s.pct > SECTOR_LIMIT_PCT:
            out.append(XRayWarning("CONC_SECTOR", "caution", "Concentrated in one sector",
                                   f"{s.name} is {s.pct:.1f}% of your portfolio."))
    if len(holdings) == 1:
        name = funds[next(iter(holdings))].name
        out.append(XRayWarning("ONE_FUND", "info", "All of your money is in one fund",
                               f"Everything is in {name}. That keeps things simple, but one fund means one strategy's risks."))
    else:
        for code, v in holdings.items():
            if v / total * 100 > FUND_LIMIT_PCT:
                out.append(XRayWarning("CONC_FUND", "caution", "Most of your money is in one fund",
                                       f"{funds[code].name} is {v / total * 100:.1f}% of your portfolio."))
    us = region.get("US", 0.0) / total * 100
    if us > HOME_LIMIT_PCT:
        out.append(XRayWarning("HOME_BIAS", "info", "Mostly in the US",
                               f"{us:.1f}% of your money is in US stocks, bonds and T-bills."))
    for o in overlaps:
        if o.shared_etfs_pct >= OVERLAP_ETF_PCT or o.shared_companies_pct >= OVERLAP_COMPANY_PCT:
            shared = f" Both hold {join_words(o.top_shared)}." if o.top_shared else ""
            out.append(XRayWarning("OVERLAP", "caution", "Two funds own the same things",
                                   f"{o.names[0]} and {o.names[1]} overlap: {overlap_words(o)}.{shared}"))
    return out
