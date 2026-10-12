from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin

PERSON_KINDS = ("investor", "advisor", "ops", "compliance", "admin")


class Person(IdMixin, Base):
    __tablename__ = "person"

    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    risk_band: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1..5, set by onboarding (Plan 3)
    firebase_uid: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
