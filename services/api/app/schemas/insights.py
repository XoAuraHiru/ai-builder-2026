from typing import Literal

from pydantic import BaseModel

from app.services.narrative import NarrativeOut


class RiskOut(BaseModel):
    window_start: str
    window_end: str
    months: int
    weights: dict[str, float]
    value_usd: float
    annual_volatility_pct: float
    beta: float
    max_drawdown_pct: float
    drawdown_peak: str
    drawdown_trough: str
    var95_1m_pct: float
    var95_1m_usd: float
    sharpe: float
    worst_month: dict
    best_month: dict
    correlations: dict[str, dict[str, float]]
    risk_contributions_pct: dict[str, float]
    portfolio_band: int
    names: dict[str, str] = {}
    profile_band: int | None
    verdict: Literal["above", "within", "below", "no_profile"]


class ExplainedRisk(BaseModel):
    report: RiskOut
    narrative: NarrativeOut


class ExposureOut(BaseModel):
    name: str
    value_usd: float
    pct: float


class EtfOut(BaseModel):
    ticker: str
    asset_class: str
    value_usd: float
    pct: float
    expense_ratio_pct: float | None


class CompanyOut(BaseModel):
    symbol: str
    name: str
    value_usd: float
    pct: float
    via: list[str]


class OverlapOut(BaseModel):
    funds: list[str]
    names: list[str]
    shared_etfs_pct: float
    shared_companies_pct: float
    top_shared: list[str]


class FeesOut(BaseModel):
    atrium_annual_usd: float
    etf_annual_usd: float
    total_annual_usd: float
    total_pct: float
    ten_year_usd: float


class WarningOut(BaseModel):
    code: str
    severity: Literal["caution", "info"]
    title: str
    message: str


class XRayOut(BaseModel):
    total_value_usd: float
    etfs: list[EtfOut]
    sectors: list[ExposureOut]
    regions: list[ExposureOut]
    asset_classes: list[ExposureOut]
    companies: list[CompanyOut]
    coverage_pct: float
    overlaps: list[OverlapOut]
    fees: FeesOut
    warnings: list[WarningOut]
    profiles_as_of: str


class ExplainedXRay(BaseModel):
    xray: XRayOut
    narrative: NarrativeOut
