"""Four-eyes approvals with step-up (blueprint D6).

A fact-changing action (publishing prices, a manual reconciliation match, a ledger reversal) is requested by one person
with a reason and the evidence. It runs only when a different person, in a role allowed to approve it, decides with a
current one-time code from their authenticator. The payload is hashed when requested and checked again before it runs,
so what was approved is exactly what happens.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime

import pyotp
from sqlalchemy.orm import Session

from app.events import emit
from app.models import Approval, Person
from app.models.base import utcnow
from app.realtime import notices

APPROVERS = {"publish_prices": ("ops", "admin"), "manual_match": ("ops", "admin"), "reverse_posting": ("ops", "admin")}

Executor = Callable[[Session, Approval, Person, datetime], dict]


class OpsError(Exception):
    """An operations action cannot go ahead; the message says why, in words the person can act on."""


class ApprovalError(OpsError):
    pass


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def ensure_totp_secret(person: Person) -> str:
    if not person.totp_secret:
        person.totp_secret = pyotp.random_base32()
    return person.totp_secret


def current_code(person: Person, now: datetime | None = None) -> tuple[str, int]:
    """The code the staff member's authenticator shows now, and the seconds it has left (the demo authenticator)."""
    totp = pyotp.TOTP(ensure_totp_secret(person))
    moment = now or utcnow()
    return totp.at(moment), totp.interval - int(moment.timestamp()) % totp.interval


def verify_code(person: Person, code: str, now: datetime | None = None) -> bool:
    if not person.totp_secret:
        return False
    digits = "".join(ch for ch in (code or "") if ch.isdigit())
    return len(digits) == 6 and pyotp.TOTP(person.totp_secret).verify(digits, for_time=now or utcnow(), valid_window=1)


def request_approval(db: Session, *, action: str, payload: dict, summary: str, reason: str, evidence: list[dict],
                     requested_by: Person) -> Approval:
    if action not in APPROVERS:
        raise ApprovalError(f"Unknown action {action}.")
    if not (reason or "").strip():
        raise ApprovalError("Give a reason: the approver reads it before deciding.")
    row = Approval(action=action, payload=payload, payload_hash=payload_hash(payload), summary=summary,
                   reason=reason.strip(), evidence=evidence, state="pending", requested_by=requested_by.id)
    db.add(row)
    db.flush()
    emit("ApprovalRequested", {"approval_id": row.id, "action": action, "requested_by": requested_by.id})
    notices.approval_requested(db, row, requested_by, APPROVERS[action])
    return row


def _executor(action: str) -> Executor:
    if action == "publish_prices":
        from app.services.fund_pricing import execute_publish

        return execute_publish
    if action == "manual_match":
        from app.services.reconciliation import execute_manual_match

        return execute_manual_match
    from app.services.reversals import execute_reversal

    return execute_reversal


def _on_reject(db: Session, approval: Approval, now: datetime) -> None:
    if approval.action == "manual_match":
        from app.services.reconciliation import reject_manual_match

        reject_manual_match(db, approval, now)


def decide(db: Session, approval: Approval, approver: Person, *, approve: bool, code: str, note: str = "",
           now: datetime | None = None, executor: Executor | None = None) -> Approval:
    now = now or utcnow()
    if approval.state != "pending":
        raise ApprovalError("This request has already been decided.")
    if approver.id == approval.requested_by:
        raise ApprovalError("A different person must approve this: you made the request.")
    if approver.kind not in APPROVERS[approval.action]:
        raise ApprovalError("Only operations staff can approve this.")
    if not verify_code(approver, code, now):
        raise ApprovalError("That code is not right or has expired. Enter the current six-digit code from your "
                            "authenticator.")
    if payload_hash(approval.payload) != approval.payload_hash:
        raise ApprovalError("The request changed after it was made, so it cannot be approved.")
    if approve:
        approval.result = (executor or _executor(approval.action))(db, approval, approver, now)
        approval.state = "approved"
    else:
        _on_reject(db, approval, now)
        approval.state = "rejected"
    approval.decided_by, approval.decided_at, approval.step_up_verified_at = approver.id, now, now
    approval.decision_note = note.strip() or None
    db.flush()
    emit("ApprovalDecided", {"approval_id": approval.id, "action": approval.action, "state": approval.state,
                             "requested_by": approval.requested_by, "decided_by": approver.id})
    notices.approval_decided(db, approval, approver)
    return approval
