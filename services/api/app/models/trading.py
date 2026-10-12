"""Trading (Plan 4): orders for shares and ETFs with the Guardian's evidence, watchlists, and the devices an account is
used from."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin, utcnow

ORDER_SIDES = ("buy", "sell")
ORDER_TYPES = ("market", "limit")
ORDER_STATES = ("held", "open", "filled", "cancelled", "rejected")
VERDICTS = ("proceed", "warn", "hold", "block")


class TradeOrder(IdMixin, Base):
    """One order for a share or an ETF. `guardian` keeps the Guardian's full report at the moment it was placed."""

    __tablename__ = "trade_order"

    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    order_type: Mapped[str] = mapped_column(String(6), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    state: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    verdict: Mapped[str] = mapped_column(String(8), nullable=False)
    guardian: Mapped[dict] = mapped_column(JSON, nullable=False)
    acknowledged_warnings: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estimated_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    fill_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    broker: Mapped[str] = mapped_column(String(16), nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trust_score: Mapped[int] = mapped_column(Integer, nullable=False)
    trust_band: Mapped[str] = mapped_column(String(10), nullable=False)
    device_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("person.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_review: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timeline: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class WatchItem(IdMixin, Base):
    __tablename__ = "watch_item"
    __table_args__ = (UniqueConstraint("person_id", "symbol"),)

    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(8), nullable=False)


class AccountDevice(IdMixin, Base):
    """A device an account has been used from. Only a hash of the browser's random identifier is stored."""

    __tablename__ = "account_device"
    __table_args__ = (UniqueConstraint("account_id", "device_hash"),)

    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"), nullable=False, index=True)
    device_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
