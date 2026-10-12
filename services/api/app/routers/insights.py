from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.llm import LLM, LLMError, get_llm
from app.auth import CurrentUser, assert_account_access, get_current_user
from app.db import get_db
from app.models import Account, Fund
from app.routers.accounts import account_or_404
from app.routers.invest import EXPLAIN_BUSY, all_funds
from app.schemas.insights import ExplainedRisk, ExplainedXRay, RiskOut, XRayOut
from app.seed.history import load_etf_document
from app.services.narrative import write_narrative
from app.services.portfolio import PortfolioView, PriceUnavailable, valuation
from app.services.risk_metrics import risk_report
from app.services.xray import xray

router = APIRouter(prefix="/accounts", tags=["insights"])
NO_HOLDINGS = "This account has no holdings yet. Invest in a fund to see this analysis."
RISK_TASK = ("Explain how risky this portfolio has been, in plain words: its typical yearly swings (volatility), its "
             "worst fall and when it happened, what a bad month could cost in dollars, how it moves with the S&P 500 "
             "(beta), and which funds drive most of the risk compared with their share of the money. Compare the "
             "portfolio's band with the reader's risk-profile band and say plainly whether it is above, within or "
             "below it, or that they have no profile yet.")
XRAY_TASK = ("Explain what the reader actually owns once you look through their funds: the largest companies and "
             "sectors, any concentration or overlap warnings, how much is in the US, and what they pay in fees each "
             "year. Be specific and calm.")


def holdings_of(db: Session, account_id: str, user: CurrentUser) -> tuple[Account, PortfolioView]:
    account = account_or_404(db, account_id)
    assert_account_access(user, account)
    try:
        view = valuation(db, account_id, date.today())
    except PriceUnavailable as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if view.total_value <= 0:
        raise HTTPException(status_code=409, detail=NO_HOLDINGS)
    return account, view


def verdict(portfolio_band: int, profile_band: int | None) -> str:
    if profile_band is None:
        return "no_profile"
    return "above" if portfolio_band > profile_band else "below" if portfolio_band < profile_band else "within"


def build_risk(db: Session, account: Account, view: PortfolioView) -> RiskOut:
    report = risk_report(all_funds(db), {c: float(v) for c, v in view.by_fund.items()}, float(view.total_value))
    band = account.person.risk_band
    return RiskOut(**asdict(report), profile_band=band, verdict=verdict(report.portfolio_band, band))


def build_xray(db: Session, view: PortfolioView) -> XRayOut:
    document = load_etf_document()
    result = xray({c: float(v) for c, v in view.by_fund.items()}, all_funds(db), document["etfs"], document["as_of"])
    return XRayOut(**asdict(result))


def risk_facts(r: RiskOut, funds: dict[str, Fund]) -> dict:
    def name(code: str) -> str:
        return funds[code].name if code in funds else code

    return {
        "history_window": f"{r.window_start} to {r.window_end}", "portfolio_value_usd": round(r.value_usd),
        "volatility_pct": r.annual_volatility_pct, "beta_to_sp500": r.beta, "worst_fall_pct": r.max_drawdown_pct,
        "worst_fall_from": r.drawdown_peak, "worst_fall_to": r.drawdown_trough,
        "bad_month_loss_pct": r.var95_1m_pct, "bad_month_loss_usd": round(r.var95_1m_usd), "sharpe_ratio": r.sharpe,
        "worst_month": r.worst_month, "best_month": r.best_month, "portfolio_band": r.portfolio_band,
        "profile_band": r.profile_band, "comparison_with_profile": r.verdict,
        "share_of_value_pct": {name(c): round(w * 100, 1) for c, w in r.weights.items()},
        "share_of_risk_pct": {name(c): v for c, v in r.risk_contributions_pct.items()},
    }


def xray_facts(x: XRayOut) -> dict:
    return {
        "total_value_usd": round(x.total_value_usd),
        "largest_companies": [{"name": c.name, "pct_of_portfolio": c.pct, "held_through": c.via} for c in x.companies[:6]],
        "sectors_pct": {s.name: s.pct for s in x.sectors[:6]}, "regions_pct": {r.name: r.pct for r in x.regions},
        "asset_classes_pct": {a.name: a.pct for a in x.asset_classes}, "warnings": [w.message for w in x.warnings],
        "fund_overlaps": [{"funds": o.names, "same_etfs_pct": o.shared_etfs_pct,
                           "same_companies_pct": o.shared_companies_pct, "shared": o.top_shared} for o in x.overlaps],
        "fees": {"total_per_year_usd": x.fees.total_annual_usd, "atrium_per_year_usd": x.fees.atrium_annual_usd,
                 "etf_costs_per_year_usd": x.fees.etf_annual_usd, "total_pct_per_year": x.fees.total_pct,
                 "ten_years_at_todays_value_usd": round(x.fees.ten_year_usd)},
        "top_holdings_cover_pct_of_stocks": x.coverage_pct,
    }


@router.get("/{account_id}/risk", response_model=RiskOut)
def risk(account_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    account, view = holdings_of(db, account_id, user)
    return build_risk(db, account, view)


@router.post("/{account_id}/risk/explain", response_model=ExplainedRisk)
def explain_risk(account_id: str, db: Session = Depends(get_db), llm: LLM = Depends(get_llm),
                 user: CurrentUser = Depends(get_current_user)):
    account, view = holdings_of(db, account_id, user)
    report = build_risk(db, account, view)
    try:
        narrative = write_narrative(db, llm, purpose="risk_narrative", agent="investor_copilot", task=RISK_TASK,
                                    audience="an investor", facts=risk_facts(report, all_funds(db)),
                                    subject_type="account", subject_id=account.id)
    except LLMError as e:
        raise HTTPException(status_code=503, detail=EXPLAIN_BUSY) from e
    db.commit()
    return ExplainedRisk(report=report, narrative=narrative)


@router.get("/{account_id}/xray", response_model=XRayOut)
def get_xray(account_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    _, view = holdings_of(db, account_id, user)
    return build_xray(db, view)


@router.post("/{account_id}/xray/explain", response_model=ExplainedXRay)
def explain_xray(account_id: str, db: Session = Depends(get_db), llm: LLM = Depends(get_llm),
                 user: CurrentUser = Depends(get_current_user)):
    account, view = holdings_of(db, account_id, user)
    result = build_xray(db, view)
    try:
        narrative = write_narrative(db, llm, purpose="xray_narrative", agent="investor_copilot", task=XRAY_TASK,
                                    audience="an investor", facts=xray_facts(result), subject_type="account",
                                    subject_id=account.id)
    except LLMError as e:
        raise HTTPException(status_code=503, detail=EXPLAIN_BUSY) from e
    db.commit()
    return ExplainedXRay(xray=result, narrative=narrative)
