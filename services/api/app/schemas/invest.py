from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.narrative import NarrativeOut


class ScenarioIn(BaseModel):
    label: str | None = Field(None, max_length=40)
    allocation: dict[str, float] = Field(min_length=1, max_length=7)

    @field_validator("allocation")
    @classmethod
    def positive_weights(cls, v: dict[str, float]) -> dict[str, float]:
        if any(w <= 0 for w in v.values()):
            raise ValueError("every weight must be positive")
        return v


class WhatIfIn(BaseModel):
    initial_usd: float = Field(0, ge=0, le=10_000_000)
    monthly_usd: float = Field(0, ge=0, le=1_000_000)
    years: int = Field(ge=1, le=40)
    goal_usd: float | None = Field(None, gt=0, le=1_000_000_000)
    scenarios: list[ScenarioIn] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def something_to_invest(self):
        if self.initial_usd == 0 and self.monthly_usd == 0:
            raise ValueError("enter a starting amount, a monthly amount, or both")
        return self


class YearPoint(BaseModel):
    year: int
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    contributed: float


class ScenarioOut(BaseModel):
    label: str
    allocation: dict[str, float]
    fee_bps: float
    yearly: list[YearPoint]
    final: dict[str, float]
    prob_goal: float | None
    prob_loss: float
    median_without_fees: float
    fee_cost: float
    history: dict


class WhatIfOut(BaseModel):
    initial_usd: float
    monthly_usd: float
    years: int
    goal_usd: float | None
    contributed: float
    window_start: str
    window_end: str
    months: int
    paths: int
    method: str
    scenarios: list[ScenarioOut]


class ExplainedWhatIf(BaseModel):
    result: WhatIfOut
    narrative: NarrativeOut
