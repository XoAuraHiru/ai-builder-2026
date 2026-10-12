from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ConstituentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ticker: str
    weight: Decimal
    asset_class: str
    region: str
    sector: str


class FundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str
    category: str
    risk_band: int
    fee_bps: int
    min_investment: Decimal
    objective: str
    who_for: str
    inception_on: date
    constituents: list[ConstituentOut]


class PriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    as_of: date
    nav: Decimal
    units_in_issue: Decimal
    status: str
