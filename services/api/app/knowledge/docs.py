"""Fund documents: one fact sheet per house fund plus a short firm document, built from fund data and real history.

The same structure renders to Markdown (committed, readable, and the source of the local search index), to HTML
(uploaded and indexed by Vertex AI Search) and to JSON for the fund pages. So what the investor reads is exactly what
the search index holds.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from app.models import Fund
from app.seed.funds import HOUSE_FUNDS, house_fund_objects
from app.seed.history import load_etf_profiles
from app.services.fund_returns import backfill_notes, constituent_weights, fund_returns, monthly_returns

BAND_LABEL = {1: "Preserve", 2: "Cautious", 3: "Balanced", 4: "Growth", 5: "Adventurous"}
REGION_NAME = {"US": "US", "DM_ex_US": "Developed ex-US", "EM": "Emerging", "Global": "Global"}
CATEGORY_RISKS = {
    "money_market": [
        "Treasury-bill ETFs are among the steadiest investments, but their prices can still dip when short-term "
        "interest rates move, and their yield can trail inflation.",
        "Unlike a bank deposit, this fund is not insured by the FDIC."],
    "income": [
        "Bond prices fall when interest rates rise, so this fund can lose value, as it did when rates rose quickly "
        "in 2022.",
        "Corporate bonds add credit risk: a company can fail to pay what it owes."],
    "balanced": [
        "With 60% in US stocks, this fund can fall sharply in a market crash, as it did in 2008.",
        "Bonds usually soften stock falls, but not always: in 2022 stocks and bonds fell together."],
    "growth": [
        "This fund is concentrated in large US growth and technology companies, so it can fall much further than "
        "the overall market.",
        "Falls of a third or more have happened in past crashes, and recoveries have taken years."],
    "global_equity": [
        "Foreign stocks add currency risk: a stronger dollar lowers the value of overseas holdings.",
        "International markets have trailed the US for long stretches, and emerging markets can be volatile."],
    "income_equity": [
        "Companies can cut their dividends, and dividend stocks can lag the market when fast-growing companies lead.",
        "This is a stock fund: it can fall sharply in a crash despite its income focus."],
    "sector": [
        "This fund holds a single sector, so it can fall far more than the overall market and stay down for years.",
        "Hold it only as a small part of a wider portfolio."],
}


@dataclass
class DocSection:
    id: str
    title: str
    paragraphs: list[str]
    table: tuple[list[str], list[list[str]]] | None = None


@dataclass
class FundDoc:
    code: str
    title: str
    sections: list[DocSection]


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def section(title: str, paragraphs: list[str], table: tuple[list[str], list[list[str]]] | None = None) -> DocSection:
    return DocSection(id=slug(title), title=title, paragraphs=paragraphs, table=table)


def month_name(year_month: str) -> str:
    return pd.Timestamp(f"{year_month}-01").strftime("%B %Y")


def fund_facts(fund: Fund, history: pd.DataFrame | None = None, profiles: dict | None = None) -> dict:
    profiles = load_etf_profiles() if profiles is None else profiles
    r = fund_returns(constituent_weights(fund), monthly_returns(history))
    yearly = (1 + r).groupby(r.index.year).prod() - 1
    counts = r.groupby(r.index.year).size()
    calendar = [{"year": int(y), "return_pct": round(float(v) * 100, 1), "months": int(counts[y])}
                for y, v in yearly.items()]
    full_years = [c for c in calendar if c["months"] == 12]
    wealth = (1 + r).cumprod()
    drawdown = wealth / wealth.cummax() - 1
    trough = drawdown.idxmin()
    peak = wealth.loc[:trough].idxmax()
    years = len(r) / 12
    etf_cost = sum(float(c.weight) * (profiles.get(c.ticker, {}).get("expense_ratio") or 0.0) for c in fund.constituents)
    atrium_pct = round(fund.fee_bps / 100, 2)
    etf_pct = round(etf_cost * 100, 2)
    total_pct = round(atrium_pct + etf_pct, 2)
    companies: dict[str, dict] = {}
    for c in fund.constituents:
        if c.asset_class != "equity":
            continue
        for h in profiles.get(c.ticker, {}).get("top_holdings", []):
            entry = companies.setdefault(h["symbol"], {"symbol": h["symbol"], "name": h["name"], "weight": 0.0})
            entry["weight"] += float(c.weight) * h["weight"]
    top = sorted(companies.values(), key=lambda e: -e["weight"])[:5]
    return {
        "window_start": f"{r.index[0]:%Y-%m}", "window_end": f"{r.index[-1]:%Y-%m}",
        "annual_return_pct": round((float(wealth.iloc[-1]) ** (1 / years) - 1) * 100, 1),
        "annual_volatility_pct": round(float(r.std(ddof=1)) * 12 ** 0.5 * 100, 1),
        "max_drawdown_pct": round(float(drawdown.min()) * 100, 1),
        "drawdown_from": f"{peak:%Y-%m}", "drawdown_to": f"{trough:%Y-%m}",
        "best_year": max(full_years, key=lambda c: c["return_pct"]),
        "worst_year": min(full_years, key=lambda c: c["return_pct"]),
        "calendar_years": calendar,
        "fees": {"atrium_pct": atrium_pct, "etf_pct": etf_pct, "total_pct": total_pct,
                 "per_10k_usd": round(total_pct * 100, 2)},
        "holdings": [{"ticker": c.ticker, "weight_pct": round(float(c.weight) * 100, 1), "asset_class": c.asset_class,
                      "region": c.region,
                      "expense_ratio_pct": (None if profiles.get(c.ticker, {}).get("expense_ratio") is None
                                            else round(profiles[c.ticker]["expense_ratio"] * 100, 2))}
                     for c in sorted(fund.constituents, key=lambda c: -float(c.weight))],
        "top_companies": [{"symbol": e["symbol"], "name": e["name"], "pct": round(e["weight"] * 100, 1)} for e in top],
        "backfill_notes": backfill_notes(fund, history),
        "growth_of_10k": [{"month": f"{d:%Y-%m}", "value": round(10_000 * float(v), 2)} for d, v in wealth.items()],
        "launched": fund.inception_on.isoformat(),
    }


@lru_cache(maxsize=16)
def cached_facts(code: str) -> dict:
    return fund_facts(house_fund_objects()[code])


def fund_doc(fund: Fund, facts: dict) -> FundDoc:
    f, fees = facts, facts["fees"]
    holdings_text = f"{fund.name} holds {len(f['holdings'])} exchange-traded funds in fixed proportions, rebalanced monthly."
    if f["top_companies"]:
        names = ", ".join(f"{c['name']} ({c['pct']:.1f}%)" for c in f["top_companies"])
        holdings_text += f" Its largest underlying companies are {names}."
    holdings_rows = [[h["ticker"], f"{h['weight_pct']:.0f}%", h["asset_class"].capitalize(),
                      REGION_NAME.get(h["region"], h["region"]),
                      "n/a" if h["expense_ratio_pct"] is None else f"{h['expense_ratio_pct']:.2f}%"] for h in f["holdings"]]
    year_rows = [[str(c["year"]) if c["months"] == 12 else f"{c['year']} ({c['months']} months)",
                  f"{c['return_pct']:+.1f}%"] for c in f["calendar_years"]]
    best, worst = f["best_year"], f["worst_year"]
    launched = pd.Timestamp(f["launched"])
    sections = [
        section("Objective", [fund.objective]),
        section("What it holds", [holdings_text],
                (["ETF", "Weight", "Asset class", "Region", "ETF expense ratio"], holdings_rows)),
        section("Who it suits", [fund.who_for,
                                 f"It is risk band {fund.risk_band} of 5 ({BAND_LABEL[fund.risk_band]}). It suits "
                                 f"investors whose risk profile is band {fund.risk_band} or higher."]),
        section("Fees", [
            f"Atrium fee: {fees['atrium_pct']:.2f}% a year, which is ${fees['atrium_pct'] * 100:.0f} on every $10,000 "
            "invested.",
            f"Underlying ETF costs: about {fees['etf_pct']:.2f}% a year, from each ETF's published expense ratio. They "
            "are already reflected in the ETF prices.",
            f"Total yearly cost: about {fees['total_pct']:.2f}%, or ${fees['per_10k_usd']:.0f} on $10,000. There are "
            "no entry, exit, switching or performance fees."]),
        section("How it behaved", [
            f"From {month_name(f['window_start'])} to {month_name(f['window_end'])}, the fund's mix returned "
            f"{f['annual_return_pct']:.1f}% a year on average before the Atrium fee, with yearly swings (volatility) of "
            f"about {f['annual_volatility_pct']:.1f}%.",
            f"Its best calendar year was {best['year']} ({best['return_pct']:+.1f}%) and its worst was {worst['year']} "
            f"({worst['return_pct']:+.1f}%).",
            f"Its largest fall from a peak was {abs(f['max_drawdown_pct']):.1f}%, from {month_name(f['drawdown_from'])} "
            f"to {month_name(f['drawdown_to'])}."], (["Year", "Return"], year_rows)),
        section("Risks", CATEGORY_RISKS[fund.category]),
        section("Important information", [
            f"The fund launched on {launched:%B} {launched.day}, {launched.year}. Figures before then are a backtest of "
            "its target mix using the ETFs' real month-end prices. " + " ".join(f["backfill_notes"]),
            "Backtests are hypothetical. Past performance does not predict future returns, and you can lose money. "
            "Atrium is a prototype with synthetic accounts and paper trading; nothing here is investment advice."]),
    ]
    return FundDoc(code=fund.code, title=f"{fund.name} ({fund.code})", sections=sections)


def firm_doc() -> FundDoc:
    fees = sorted(spec["fee_bps"] for spec in HOUSE_FUNDS)
    return FundDoc(code="ATRIUM", title="Why Atrium", sections=[
        section("How Atrium invests", [
            "Atrium offers seven house funds. Each one is a fixed mix of low-cost exchange-traded funds (ETFs) listed "
            "in the US, rebalanced monthly, ranging from a Treasury-bill reserve (risk band 1) to a technology fund "
            "(risk band 5).",
            "Every investor gets a risk profile with a band from 1 to 5, and Atrium checks each instruction against it "
            "before accepting it."]),
        section("Clear fees", [
            f"Each fund has one yearly Atrium fee, between {fees[0] / 100:.2f}% and {fees[-1] / 100:.2f}%, plus the "
            "costs of the underlying ETFs. There are no entry, exit, switching or performance fees."]),
        section("Everything explained", [
            "Every score, projection and recommendation in Atrium shows why: the evidence, the method and, where AI "
            "wrote the words, which model wrote them.",
            "Projections come from a simulation engine run over real market history since 2007, not from the AI."]),
        section("How Atrium protects you", [
            "Atrium checks identity and fraud signals from the first contact, before an account is opened.",
            "Instructions that would take you above your risk profile need your explicit confirmation."]),
        section("Important information", [
            "Atrium is a prototype built for the AI Builder Cup 2026. Its people and accounts are synthetic and all "
            "trading is on paper. Nothing here is investment advice."]),
    ])


def to_markdown(doc: FundDoc) -> str:
    lines = [f"# {doc.title}", ""]
    for s in doc.sections:
        lines += [f"## {s.title}", ""]
        for p in s.paragraphs:
            lines += [p, ""]
        if s.table:
            head, rows = s.table
            lines.append("| " + " | ".join(head) + " |")
            lines.append("|" + "|".join(" --- " for _ in head) + "|")
            lines += ["| " + " | ".join(row) + " |" for row in rows]
            lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def to_html(doc: FundDoc) -> str:
    e = html.escape
    parts = ["<!doctype html>", '<html lang="en">', "<head>", '<meta charset="utf-8">', f"<title>{e(doc.title)}</title>",
             "</head>", "<body>", f"<h1>{e(doc.title)}</h1>"]
    for s in doc.sections:
        parts += [f'<section id="{s.id}">', f"<h2>{e(s.title)}</h2>"]
        parts += [f"<p>{e(p)}</p>" for p in s.paragraphs]
        if s.table:
            head, rows = s.table
            parts.append("<table><thead><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr></thead><tbody>")
            parts += ["<tr>" + "".join(f"<td>{e(c)}</td>" for c in row) + "</tr>" for row in rows]
            parts.append("</tbody></table>")
        parts.append("</section>")
    parts += ["</body>", "</html>"]
    return "\n".join(parts) + "\n"


def build_all() -> list[FundDoc]:
    funds = house_fund_objects()
    return [fund_doc(f, fund_facts(f)) for f in funds.values()] + [firm_doc()]
