"""Fraud ring radar: a person's decision to flag a lead as part of a ring (trust signal T09)."""
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin


class RingFlag(IdMixin, Base):
    """One lead flagged as a member of one ring, by a compliance person. A lead is flagged at most once per ring."""

    __tablename__ = "ring_flag"
    __table_args__ = (UniqueConstraint("lead_id", "ring_id"),)

    lead_id: Mapped[str] = mapped_column(ForeignKey("lead.id"), nullable=False, index=True)
    ring_id: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    flagged_by: Mapped[str] = mapped_column(ForeignKey("person.id"), nullable=False)
