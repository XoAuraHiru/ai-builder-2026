from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class InstructionIn(BaseModel):
    type: Literal["subscribe", "redeem", "switch"]
    fund_code: str
    to_fund_code: str | None = None
    amount_usd: Decimal | None = Field(None, gt=0, le=10_000_000)
    units: Decimal | None = Field(None, gt=0)
    acknowledge_risk: bool = False
    analysis_id: str | None = Field(None, max_length=32)

    @model_validator(mode="after")
    def shape(self):
        if self.type == "subscribe" and (self.amount_usd is None or self.units is not None):
            raise ValueError("an investment needs a dollar amount")
        if self.type in ("redeem", "switch") and (self.amount_usd is None) == (self.units is None):
            raise ValueError("give either a dollar amount or a number of units")
        if self.type == "switch" and (not self.to_fund_code or self.to_fund_code == self.fund_code):
            raise ValueError("choose a different fund to switch into")
        if self.type != "switch" and self.to_fund_code:
            raise ValueError("only a switch has a target fund")
        return self


class CheckOut(BaseModel):
    code: str
    ok: bool
    message: str


class RedemptionOut(BaseModel):
    units: Decimal
    value: Decimal
    cost: Decimal
    realised_gain: Decimal
    nav: Decimal
    nav_as_of: date
    lots: list[dict]


class PlanOut(BaseModel):
    ok: bool
    checks: list[CheckOut]
    needs_acknowledgement: bool
    suitability: str | None
    estimate: dict
    redemption: RedemptionOut | None


class StepOut(BaseModel):
    state: str
    note: str
    at: datetime


class InstructionOut(BaseModel):
    id: str
    type: str
    fund_code: str
    fund_name: str
    to_fund_code: str | None
    to_fund_name: str | None
    amount: Decimal | None
    units: Decimal | None
    state: str
    acknowledged_risk: bool
    requested_at: datetime
    steps: list[StepOut]
    payment_reference: str | None = None


class RecurringIn(BaseModel):
    fund_code: str
    amount_usd: Decimal = Field(gt=0, le=1_000_000)
    day_of_month: int = Field(ge=1, le=28)
    acknowledge_risk: bool = False
    analysis_id: str | None = Field(None, max_length=32)


class RecurringOut(BaseModel):
    id: str
    fund_code: str
    fund_name: str
    amount: Decimal
    day_of_month: int
    status: str
    acknowledged_risk: bool
    created_at: datetime
