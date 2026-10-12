from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fund, FundConstituent

# Each constituent is (ticker, weight, asset_class, region, sector).
HOUSE_FUNDS: list[dict] = [
    dict(code="ATR-CASH", name="Atrium Cash Reserve", category="money_market", risk_band=1, fee_bps=10, min_investment="100",
         objective="Preserve capital and earn short-term Treasury yields with daily liquidity.",
         who_for="Emergency funds, parking cash between investments, horizons under one year.",
         constituents=[("SGOV", "0.6", "cash", "US", "treasury"), ("BIL", "0.4", "cash", "US", "treasury")]),
    dict(code="ATR-INC", name="Atrium Core Income", category="income", risk_band=2, fee_bps=25, min_investment="500",
         objective="Steady income from a diversified portfolio of US investment-grade bonds.",
         who_for="Income seekers and investors with horizons of one to three years.",
         constituents=[("BND", "0.5", "bond", "US", "aggregate"), ("AGG", "0.3", "bond", "US", "aggregate"),
                       ("VCIT", "0.2", "bond", "US", "corporate")]),
    dict(code="ATR-BAL", name="Atrium Balanced", category="balanced", risk_band=3, fee_bps=35, min_investment="500",
         objective="Balanced growth and income through a 60/40 mix of US equities and bonds.",
         who_for="Medium horizons of three to seven years and moderate loss tolerance.",
         constituents=[("VTI", "0.6", "equity", "US", "broad"), ("BND", "0.4", "bond", "US", "aggregate")]),
    dict(code="ATR-GRW", name="Atrium Growth", category="growth", risk_band=4, fee_bps=40, min_investment="500",
         objective="Long-term capital growth from large-cap and growth-oriented US equities.",
         who_for="Long horizons over seven years and higher loss tolerance.",
         constituents=[("VOO", "0.5", "equity", "US", "broad"), ("QQQ", "0.3", "equity", "US", "technology"),
                       ("VUG", "0.2", "equity", "US", "growth")]),
    dict(code="ATR-GLB", name="Atrium Global Equity", category="global_equity", risk_band=4, fee_bps=40, min_investment="500",
         objective="Diversified growth from developed and emerging markets outside and including the US.",
         who_for="Investors who want exposure beyond the US with long horizons.",
         constituents=[("VT", "0.5", "equity", "Global", "broad"), ("VXUS", "0.3", "equity", "DM_ex_US", "broad"),
                       ("VEA", "0.2", "equity", "DM_ex_US", "broad")]),
    dict(code="ATR-DIV", name="Atrium Dividend", category="income_equity", risk_band=3, fee_bps=35, min_investment="500",
         objective="Growing income and moderate growth from quality US dividend payers.",
         who_for="Investors who want income with equity growth and medium to long horizons.",
         constituents=[("SCHD", "0.6", "equity", "US", "dividend"), ("VYM", "0.4", "equity", "US", "dividend")]),
    dict(code="ATR-TEC", name="Atrium Technology", category="sector", risk_band=5, fee_bps=50, min_investment="1000",
         objective="Concentrated growth from the US technology sector.",
         who_for="Thematic conviction as a small satellite allocation; high loss tolerance.",
         constituents=[("XLK", "0.6", "equity", "US", "technology"), ("VGT", "0.4", "equity", "US", "technology")]),
]

INCEPTION = date(2024, 10, 1)


def seed_funds(db: Session) -> list[Fund]:
    """Insert or update the seven house funds. Safe to run repeatedly."""
    out: list[Fund] = []
    for spec in HOUSE_FUNDS:
        fund = db.scalar(select(Fund).where(Fund.code == spec["code"]))
        if fund is None:
            fund = Fund(code=spec["code"], inception_on=INCEPTION)
            db.add(fund)
        fund.name = spec["name"]
        fund.category = spec["category"]
        fund.risk_band = spec["risk_band"]
        fund.fee_bps = spec["fee_bps"]
        fund.min_investment = Decimal(spec["min_investment"])
        fund.objective = spec["objective"]
        fund.who_for = spec["who_for"]
        fund.constituents = [
            FundConstituent(ticker=t, weight=Decimal(w), asset_class=a, region=r, sector=s)
            for (t, w, a, r, s) in spec["constituents"]
        ]
        out.append(fund)
    db.flush()
    return out


def all_tickers() -> list[str]:
    seen: list[str] = []
    for spec in HOUSE_FUNDS:
        for ticker, *_rest in spec["constituents"]:
            if ticker not in seen:
                seen.append(ticker)
    return seen


def house_fund_objects() -> dict[str, Fund]:
    """The seven house funds as transient objects (no session), for tools and tests that run without a database."""
    out: dict[str, Fund] = {}
    for spec in HOUSE_FUNDS:
        out[spec["code"]] = Fund(
            code=spec["code"], name=spec["name"], category=spec["category"], risk_band=spec["risk_band"],
            fee_bps=spec["fee_bps"], min_investment=Decimal(spec["min_investment"]), objective=spec["objective"],
            who_for=spec["who_for"], inception_on=INCEPTION,
            constituents=[FundConstituent(ticker=t, weight=Decimal(w), asset_class=a, region=r, sector=s)
                          for (t, w, a, r, s) in spec["constituents"]])
    return out
