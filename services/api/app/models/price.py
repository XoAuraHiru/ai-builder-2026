from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin

PRICE_STATUSES = ("draft", "checked", "published")


class Price(IdMixin, Base):
    __tablename__ = "price"
    __table_args__ = (UniqueConstraint("fund_code", "as_of", name="uq_price_fund_asof"),)

    fund_code: Mapped[str] = mapped_column(ForeignKey("fund.code"), nullable=False, index=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    nav: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    units_in_issue: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
