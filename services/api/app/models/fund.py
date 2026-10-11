from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import IdMixin

FUND_CATEGORIES = ("money_market", "income", "balanced", "growth", "global_equity", "income_equity", "sector")


class Fund(Base):
    __tablename__ = "fund"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    risk_band: Mapped[int] = mapped_column(Integer, nullable=False)
    fee_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    min_investment: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    who_for: Mapped[str] = mapped_column(Text, nullable=False)
    inception_on: Mapped[date] = mapped_column(Date, nullable=False)

    constituents: Mapped[list["FundConstituent"]] = relationship(
        back_populates="fund", cascade="all, delete-orphan", order_by="FundConstituent.weight.desc()", lazy="selectin"
    )


class FundConstituent(IdMixin, Base):
    __tablename__ = "fund_constituent"

    fund_code: Mapped[str] = mapped_column(ForeignKey("fund.code"), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(12), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(16), nullable=False)  # equity | bond | cash
    region: Mapped[str] = mapped_column(String(16), nullable=False)  # US | DM_ex_US | EM | Global
    sector: Mapped[str] = mapped_column(String(24), nullable=False)  # broad | technology | dividend | treasury | ...

    fund = relationship("Fund", back_populates="constituents")
