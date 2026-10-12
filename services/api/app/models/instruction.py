from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin, utcnow

INSTRUCTION_TYPES = ("subscribe", "redeem", "switch")
INSTRUCTION_STATES = ("received", "accepted", "priced", "allocated", "settled", "rejected", "reversed")
STEP_STATES = ("received", "checked", "accepted", "funded", "priced", "allocated", "settled", "rejected", "reversed")


class Instruction(IdMixin, Base):
    __tablename__ = "instruction"

    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"), nullable=False, index=True)
    fund_code: Mapped[str] = mapped_column(ForeignKey("fund.code"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(12), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)  # cash in for subscribe
    units: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)  # units out for redeem and switch
    state: Mapped[str] = mapped_column(String(12), nullable=False, default="received")
    dealing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_fund_code: Mapped[str | None] = mapped_column(ForeignKey("fund.code"), nullable=True)  # target of a switch
    acknowledged_risk: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class InstructionStep(IdMixin, Base):
    """The instruction's timeline: one row per state reached, with what was checked or decided."""

    __tablename__ = "instruction_step"

    instruction_id: Mapped[str] = mapped_column(ForeignKey("instruction.id"), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(12), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")


class RecurringPlan(IdMixin, Base):
    """A monthly contribution the investor set up. The day-end job (Plan 5) turns each due plan into a subscription."""

    __tablename__ = "recurring_plan"

    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"), nullable=False, index=True)
    fund_code: Mapped[str] = mapped_column(ForeignKey("fund.code"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    day_of_month: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="active")  # active | cancelled
    acknowledged_risk: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
