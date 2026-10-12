from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin


class RiskProfile(IdMixin, Base):
    """One completed risk profile. The newest row is current; older rows are the history."""

    __tablename__ = "risk_profile"

    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), nullable=False, index=True)
    band: Mapped[int] = mapped_column(Integer, nullable=False)
    capacity_band: Mapped[int] = mapped_column(Integer, nullable=False)
    tolerance_band: Mapped[int] = mapped_column(Integer, nullable=False)
    answers: Mapped[dict] = mapped_column(JSON, nullable=False)
    reasons: Mapped[list] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # questionnaire | conversation
