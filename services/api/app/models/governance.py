"""Model governance (the Model Risk Office): evaluation runs, their cases, and each model's circuit breaker."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin, utcnow

EVAL_TIERS = ("free", "live")
EVAL_TRIGGERS = ("deploy", "button", "local")
RUN_STATES = ("running", "finished", "failed")
CASE_OUTCOMES = ("pass", "fail", "error")
SUITE_KINDS = ("golden", "red_team", "fairness", "challenger")
BREAKER_STATES = ("closed", "open")


class EvalRun(IdMixin, Base):
    __tablename__ = "eval_run"

    tier: Mapped[str] = mapped_column(String(8), nullable=False)
    trigger: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    git_sha: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    requested_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    models: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # model key -> version
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("0"))
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class EvalCase(IdMixin, Base):
    __tablename__ = "eval_case"

    run_id: Mapped[str] = mapped_column(ForeignKey("eval_run.id"), nullable=False, index=True)
    model_key: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    suite: Mapped[str] = mapped_column(String(16), nullable=False)
    tier: Mapped[str] = mapped_column(String(8), nullable=False)
    case_id: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    expected: Mapped[dict | list | str | float | None] = mapped_column(JSON, nullable=True)
    actual: Mapped[dict | list | str | float | None] = mapped_column(JSON, nullable=True)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("0"))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ModelBreaker(Base):
    __tablename__ = "model_breaker"

    model_key: Mapped[str] = mapped_column(String(40), primary_key=True)
    state: Mapped[str] = mapped_column(String(8), nullable=False, default="closed")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    changed_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # [{state, reason, by, at, run_id}]
