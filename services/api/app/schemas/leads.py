from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceOfFunds = Literal["salary", "business", "savings", "inheritance", "property_sale", "investments", "other",
                        "unspecified"]


class LeadIn(BaseModel):
    source: Literal["web", "referral", "email", "chat", "event"] = "web"
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=32)
    country: str = Field(default="US", pattern=r"^[A-Z]{2}$")
    goals: str = Field(min_length=3, max_length=1000)
    horizon_years: int = Field(ge=0, le=50)
    investable_usd: Decimal = Field(ge=0, le=100_000_000)
    monthly_usd: Decimal = Field(default=Decimal("0"), ge=0, le=10_000_000)
    source_of_funds: SourceOfFunds = "unspecified"
    notes: str | None = Field(default=None, max_length=2000)
    device_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")


class LeadAck(BaseModel):
    id: str
    status: str


class StageIn(BaseModel):
    stage: Literal["new", "qualified", "proposal", "onboarding", "disqualified"]


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    source: str
    stage: str
    full_name: str
    email: str
    phone: str | None
    country: str
    goals: str
    horizon_years: int
    investable_usd: Decimal
    monthly_usd: Decimal
    source_of_funds: str
    notes: str | None
    enrichment: dict | None
    lead_score: int | None
    lead_score_factors: dict | None
    trust_score: int | None
    trust_band: str | None
    trust_signals: list | None
    next_best_action: str | None
    scored_at: datetime | None
    scoring_error: str | None
    converted_person_id: str | None


class IdentityCheckOut(BaseModel):
    id: str
    extracted: dict
    fraud_signals: dict | None
    findings: list
    source: str
    trust_score: int
    trust_band: str


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class ConvertIn(BaseModel):
    override_reason: str | None = Field(default=None, max_length=500)
