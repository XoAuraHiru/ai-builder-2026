from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin

LEAD_STAGES = ("new", "qualified", "proposal", "onboarding", "client", "disqualified")
LEAD_SOURCES = ("web", "referral", "email", "chat", "event")


class Lead(IdMixin, Base):
    __tablename__ = "lead"

    source: Mapped[str] = mapped_column(String(16), nullable=False)
    stage: Mapped[str] = mapped_column(String(16), nullable=False, default="new", index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    goals: Mapped[str] = mapped_column(Text, nullable=False)
    horizon_years: Mapped[int] = mapped_column(Integer, nullable=False)
    investable_usd: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    monthly_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    source_of_funds: Mapped[str] = mapped_column(String(20), nullable=False, default="unspecified")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("person.id"), nullable=True)
    # Filled by the AI pipeline. Null scored_at means "not scored yet".
    enrichment: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    lead_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_score_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trust_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trust_band: Mapped[str | None] = mapped_column(String(12), nullable=True)
    trust_signals: Mapped[list | None] = mapped_column(JSON, nullable=True)
    next_best_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scoring_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    converted_person_id: Mapped[str | None] = mapped_column(ForeignKey("person.id"), nullable=True)


class IdentityCheck(IdMixin, Base):
    """Result of analysing one uploaded identity document. The image itself is never stored."""

    __tablename__ = "identity_check"

    lead_id: Mapped[str] = mapped_column(ForeignKey("lead.id"), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(40), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted: Mapped[dict] = mapped_column(JSON, nullable=False)
    fraud_signals: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    findings: Mapped[list] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
