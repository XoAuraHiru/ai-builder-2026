from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin

POSTING_TYPES = ("subscription", "redemption", "buy", "sell", "deposit", "reversal", "adjustment")
INSTRUMENT_TYPES = ("fund", "equity", "cash")


class Posting(IdMixin, Base):
    """One immutable movement of units and/or cash on an account. Never updated, never deleted."""

    __tablename__ = "posting"

    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"), nullable=False, index=True)
    instrument: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # fund code or ticker
    instrument_type: Mapped[str] = mapped_column(String(8), nullable=False)
    posting_type: Mapped[str] = mapped_column(String(16), nullable=False)
    units: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)  # signed
    cash: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)  # signed, USD
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    realised_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)  # FIFO cost released by a sale
    value_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(64), nullable=False)
    reversal_of: Mapped[str | None] = mapped_column(ForeignKey("posting.id"), nullable=True)


class Lot(IdMixin, Base):
    """A tax lot opened by a positive posting and consumed FIFO by negative postings."""

    __tablename__ = "lot"

    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"), nullable=False, index=True)
    instrument: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    units_initial: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    units_remaining: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    cost_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    acquired_on: Mapped[date] = mapped_column(Date, nullable=False)
    posting_id: Mapped[str] = mapped_column(ForeignKey("posting.id"), nullable=False)
