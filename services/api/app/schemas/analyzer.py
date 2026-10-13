from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.invest import ScenarioOut, WhatIfOut
from app.services.narrative import NarrativeOut


class AnalyzeIn(BaseModel):
    kind: Literal["unit_trust", "share"]
    code: str = Field(min_length=1, max_length=16)
    initial_usd: float = Field(ge=0, le=10_000_000)
    monthly_usd: float = Field(0, ge=0, le=1_000_000)
    years: int = Field(ge=0, le=100)  # the analyzer's own rule (1 to 40) answers in words; this only bounds the input
    device_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")


class FundOption(BaseModel):
    code: str
    name: str
    risk_band: int
    fee_bps: int
    min_investment: float


class ShareOption(BaseModel):
    symbol: str
    name: str
    kind: Literal["stock", "etf"]
    history_start: str


class AnalyzerOptions(BaseModel):
    funds: list[FundOption]
    shares: list[ShareOption]
    min_share_years: int
    monthly_minimum: float


class AnalysisOut(BaseModel):
    id: str
    kind: Literal["unit_trust", "share"]
    code: str
    name: str
    fee_bps: float
    min_investment: float
    result: WhatIfOut
    comparison: ScenarioOut | None


class ExplainedAnalysis(BaseModel):
    narrative: NarrativeOut
