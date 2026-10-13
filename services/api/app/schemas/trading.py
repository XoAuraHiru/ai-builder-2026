"""API shapes for markets, the Pre-trade Guardian and orders."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.markets.quotes import MarketSession, Quote
from app.services.narrative import NarrativeOut


class SessionOut(BaseModel):
    is_open: bool
    label: str
    next_open: datetime


class QuoteOut(BaseModel):
    symbol: str
    price: Decimal
    previous_close: Decimal
    change: Decimal
    change_pct: float
    as_of: datetime
    source: Literal["live", "close"]


def session_out(s: MarketSession) -> SessionOut:
    return SessionOut(is_open=s.is_open, label=s.label, next_open=s.next_open)


def quote_out(q: Quote) -> QuoteOut:
    return QuoteOut(symbol=q.symbol, price=q.price, previous_close=q.previous_close, change=q.change,
                    change_pct=q.change_pct, as_of=q.as_of, source=q.source)


class MarketRow(BaseModel):
    symbol: str
    name: str
    kind: str
    sector: str | None
    risk_band: int
    price: Decimal
    change_pct: float
    source: str
    watched: bool


class MarketsOut(BaseModel):
    session: SessionOut
    as_of: datetime | None
    rows: list[MarketRow]


class PricePoint(BaseModel):
    day: date
    close: float


class MarketDetailOut(BaseModel):
    symbol: str
    name: str
    kind: str
    sector: str | None
    industry: str | None
    summary: str
    risk_band: int
    volatility_pct: float
    market_value: float | None
    avg_volume: float | None
    quote: QuoteOut
    session: SessionOut
    history: list[PricePoint]
    watched: bool


class OrderIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=8)
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"] = "market"
    quantity: int = Field(ge=1, le=100_000)
    limit_price: Decimal | None = Field(default=None, gt=0, le=1_000_000)
    acknowledge_warnings: bool = False
    analysis_id: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def _limit_needs_a_price(self):
        if self.order_type == "limit" and self.limit_price is None:
            raise ValueError("a limit order needs a limit price")
        return self


class CheckOut(BaseModel):
    code: str
    title: str
    outcome: Literal["pass", "info", "warn", "hold", "block"]
    detail: str


class SignalOut(BaseModel):
    code: str
    label: str
    weight: int
    evidence: str
    source: str
    blocking: bool = False


class TrustOut(BaseModel):
    score: int
    band: str
    signals: list[SignalOut]


class EstimateOut(BaseModel):
    quote: Decimal
    price: Decimal
    value: Decimal
    spread_cost: Decimal
    cash_after: Decimal
    units_after: Decimal


class OrderWords(BaseModel):
    symbol: str
    side: str
    order_type: str
    quantity: int
    limit_price: Decimal | None
    words: str


class InstrumentBrief(BaseModel):
    symbol: str
    name: str
    kind: str
    risk_band: int
    sector_label: str | None
    volatility_pct: float


class GuardianOut(BaseModel):
    verdict: Literal["proceed", "warn", "hold", "block"]
    order: OrderWords
    instrument: InstrumentBrief
    quote: QuoteOut
    session: SessionOut
    estimate: EstimateOut
    checks: list[CheckOut]
    trust: TrustOut
    takeover: bool


class ExplainedOrder(BaseModel):
    report: GuardianOut
    narrative: NarrativeOut


class StepOut(BaseModel):
    state: str
    note: str
    at: datetime


class OrderOut(BaseModel):
    id: str
    account_id: str
    account_number: str
    client_name: str
    symbol: str
    name: str
    side: str
    order_type: str
    quantity: int
    limit_price: Decimal | None
    state: str
    verdict: str
    acknowledged_warnings: bool
    estimated_value: Decimal
    fill_price: Decimal | None
    filled_at: datetime | None
    broker: str
    trust_score: int
    trust_band: str
    created_at: datetime
    timeline: list[StepOut]
    guardian: dict
    review_note: str | None
    reviewed_by_name: str | None
    ai_review: dict | None


class OrdersOut(BaseModel):
    cash: Decimal
    cash_free: Decimal
    orders: list[OrderOut]


class DecisionIn(BaseModel):
    note: str = Field(default="", max_length=500)
