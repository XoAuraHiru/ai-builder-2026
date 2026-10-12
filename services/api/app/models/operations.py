"""Operations and compliance (Plan 5): four-eyes approvals, bank statements and their lines, reconciliation matches,
AML alerts (each alert is also its case) and the day-end run log."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin

APPROVAL_ACTIONS = ("publish_prices", "manual_match", "reverse_posting")
APPROVAL_STATES = ("pending", "approved", "rejected")
LINE_STATES = ("unmatched", "proposed", "matched", "ignored")
MATCH_TIERS = ("exact_reference", "unique_amount", "fuzzy", "combination", "manual")
MATCH_STATES = ("proposed", "accepted", "rejected", "awaiting_approval")
ALERT_STATES = ("open", "escalated", "closed")
ALERT_SEVERITIES = ("high", "medium", "low")


class Approval(IdMixin, Base):
    """A fact-changing action waiting for a second person (blueprint D6). The payload is fixed when it is requested and
    its hash is checked again on approval, so what was approved is exactly what runs."""

    __tablename__ = "approval"

    action: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    state: Mapped[str] = mapped_column(String(10), nullable=False, default="pending", index=True)
    requested_by: Mapped[str] = mapped_column(ForeignKey("person.id"), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("person.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_up_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class BankStatement(IdMixin, Base):
    """One uploaded statement of Atrium's client money account."""

    __tablename__ = "bank_statement"

    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(60), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # documentai | csv
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    account_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("person.id"), nullable=False)
    notes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class StatementLine(IdMixin, Base):
    """A transaction on a statement: deposits are positive, withdrawals negative. Remitter, reference and channel are
    the normalised reading of the bank's narration."""

    __tablename__ = "statement_line"

    statement_id: Mapped[str] = mapped_column(ForeignKey("bank_statement.id"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    value_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    remitter: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(24), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    state: Mapped[str] = mapped_column(String(12), nullable=False, default="unmatched", index=True)


class ReconMatch(IdMixin, Base):
    """A proposed or confirmed pairing of statement lines with subscriptions, with its tier, confidence and evidence."""

    __tablename__ = "recon_match"

    line_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    instruction_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    proposed_by: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed", index=True)
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("person.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_id: Mapped[str | None] = mapped_column(ForeignKey("approval.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AmlAlert(IdMixin, Base):
    """An alert from transaction monitoring, with the exact rows behind it. The MLRO escalates or closes it."""

    __tablename__ = "aml_alert"

    scenario: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), nullable=False, index=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("account.id"), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(10), nullable=False, default="open", index=True)
    ai_review: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("person.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class OpsRun(IdMixin, Base):
    """One day-end run: each step's outcome and the morning brief."""

    __tablename__ = "ops_run"

    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
