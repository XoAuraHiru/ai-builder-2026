from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.funds import FundOut


class SectionOut(BaseModel):
    id: str
    title: str
    paragraphs: list[str]
    table: dict | None


class FundExplainerOut(BaseModel):
    fund: FundOut
    facts: dict
    sections: list[SectionOut]


class FundStatsOut(BaseModel):
    code: str
    name: str
    risk_band: int
    annual_return_pct: float
    annual_volatility_pct: float
    max_drawdown_pct: float
    best_year: dict
    worst_year: dict
    total_fee_pct: float
    window_start: str
    window_end: str


class FitPoint(BaseModel):
    text: str = Field(max_length=500)
    citations: list[str] = Field(default_factory=list, max_length=5)


class FitDraft(BaseModel):
    headline: str = Field(max_length=240)
    points: list[FitPoint] = Field(min_length=1, max_length=4)
    caution: str = Field(default="", max_length=400)


class CitationOut(BaseModel):
    id: str
    title: str
    text: str


class SuitabilityOut(BaseModel):
    fund_band: int
    your_band: int | None
    verdict: Literal["above", "within", "no_profile"]


class FitOut(BaseModel):
    headline: str
    points: list[FitPoint]
    caution: str
    citations: list[CitationOut]
    suitability: SuitabilityOut
    retriever: str
    unsupported_figures: list[str]
    verified: bool
    model: str
