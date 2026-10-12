from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin


class Proposal(IdMixin, Base):
    """A personalised proposal drafted for a lead: a draft for the advisor to review, never sent automatically."""

    __tablename__ = "proposal"

    lead_id: Mapped[str] = mapped_column(ForeignKey("lead.id"), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    band: Mapped[int] = mapped_column(Integer, nullable=False)
    allocation: Mapped[dict] = mapped_column(JSON, nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    compliance: Mapped[dict] = mapped_column(JSON, nullable=False)
    unsupported_figures: Mapped[list] = mapped_column(JSON, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
