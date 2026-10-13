"""Call intelligence: one reading of one recorded client call. The audio itself is never stored."""
from sqlalchemy import JSON, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin

CALL_SOURCES = ("upload", "demo")


class LeadCall(IdMixin, Base):
    __tablename__ = "lead_call"

    lead_id: Mapped[str] = mapped_column(ForeignKey("lead.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(8), nullable=False)  # upload | demo
    duration_s: Mapped[float] = mapped_column(Float, nullable=False)
    reading: Mapped[dict] = mapped_column(JSON, nullable=False)   # the grounded CallReading
    dropped: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # what grounding removed, by kind
    applied: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # [{field, value, by, at}]
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    decision_id: Mapped[str | None] = mapped_column(ForeignKey("ai_decision.id"), nullable=True)
