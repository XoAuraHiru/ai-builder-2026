from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class HoldingOut(BaseModel):
    instrument: str
    name: str
    units: Decimal
    price: Decimal
    price_as_of: date
    value: Decimal
    cost_basis: Decimal
    pnl: Decimal
    pnl_pct: Decimal


class PortfolioOut(BaseModel):
    account_id: str
    as_of: date
    total_value: Decimal
    total_cost: Decimal
    pnl: Decimal
    pnl_pct: Decimal
    holdings: list[HoldingOut]
    by_fund: dict[str, Decimal]
    by_asset_class: dict[str, Decimal]
    by_region: dict[str, Decimal]
