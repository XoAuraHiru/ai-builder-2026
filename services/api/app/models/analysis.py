from decimal import Decimal

from sqlalchemy import JSON, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin

ANALYSIS_KINDS = ("unit_trust", "share")


class Analysis(IdMixin, Base):
    """One run of the return analyzer: its inputs and headline figures. The rate limit counts these rows, and a lead,
    fund order, monthly plan or share order made from an analysis points back to it. Rerunning the inputs gives the
    same figures, because the simulation's seed comes from them."""
    __tablename__ = "analysis"

    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    initial_usd: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    monthly_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    years: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    person_id: Mapped[str | None] = mapped_column(ForeignKey("person.id"), nullable=True, index=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
