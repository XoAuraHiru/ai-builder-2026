from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import IdMixin


class Account(IdMixin, Base):
    __tablename__ = "account"

    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="individual")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    bank_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    bank_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bank_index: Mapped[str | None] = mapped_column(String(64), nullable=True)  # HMAC of the full bank account number
    opened_on: Mapped[date] = mapped_column(Date, nullable=False)

    person = relationship("Person", lazy="joined")
