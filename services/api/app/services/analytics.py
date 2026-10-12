"""Risk and X-ray inputs for a whole account: house funds plus the shares, ETFs and cash it holds directly.

House funds come from the database. Every tradable symbol, and cash, is a one-line fund (app.markets.universe), so the
risk engine and the X-ray read a share held directly exactly as they read a fund.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.markets.universe import analytics_returns, holding_objects, xray_profiles
from app.models import Fund
from app.seed.history import load_etf_document
from app.services.portfolio import PortfolioView
from app.services.risk_metrics import RiskReport, risk_report
from app.services.xray import XRay, xray


def universe(db: Session) -> dict[str, Fund]:
    return {**holding_objects(), **{f.code: f for f in db.scalars(select(Fund)).all()}}


def weights_of(view: PortfolioView) -> dict[str, float]:
    return {code: float(value) for code, value in view.by_instrument.items() if value > 0}


def direct_holdings(view: PortfolioView) -> frozenset[str]:
    """Shares and cash held directly. ETFs bought directly stay ETFs in the X-ray."""
    return frozenset(h.instrument for h in view.holdings if h.kind in ("stock", "cash"))


def portfolio_risk(funds: dict[str, Fund], view: PortfolioView) -> RiskReport:
    return risk_report(funds, weights_of(view), float(view.total_value), analytics_returns())


def portfolio_xray(funds: dict[str, Fund], view: PortfolioView) -> XRay:
    return xray(weights_of(view), funds, xray_profiles(), load_etf_document()["as_of"], direct=direct_holdings(view))
