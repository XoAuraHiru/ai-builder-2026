from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin, utcnow

INSTRUCTION_TYPES = ("subscribe", "redeem", "switch")
INSTRUCTION_STATES = ("received", "accepted", "priced", "allocated", "settled", "rejected")


class Instruction(IdMixin, Base):
    __tablename__ = "instruction"

    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"), nullable=False, index=True)
    fund_code: Mapped[str] = mapped_column(ForeignKey("fund.code"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(12), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)  # cash in for subscribe
    units: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)  # units out for redeem
    state: Mapped[str] = mapped_column(String(12), nullable=False, default="received")
    dealing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
