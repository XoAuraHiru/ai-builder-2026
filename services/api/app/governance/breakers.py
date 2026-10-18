"""Circuit breakers: a model that fails validation, or that people stop agreeing with, is switched off, and its feature
falls back to its deterministic part until a compliance person resets it with a reason and a one-time code.

Checks fail to the fallback, never to the model: if the breaker table cannot be read, the breaker counts as open.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.ai.decisions import record_decision
from app.ai.llm import LLMResult
from app.events import emit
from app.governance.inventory import MODELS
from app.models import ModelBreaker, Person
from app.models.base import utcnow
from app.realtime import notices
from app.services.approvals import verify_code


class BreakerError(ValueError):
    """A breaker change that cannot be made: an unknown model, no reason, a wrong code, nothing to reset."""


class BreakerOpen(RuntimeError):
    """Raised by a feature whose model is switched off; the message is what the page shows."""

    def __init__(self, key: str, message: str):
        super().__init__(message)
        self.key = key


def _row(db: Session, key: str) -> ModelBreaker | None:
    return db.get(ModelBreaker, key)


def breaker_open(db: Session, key: str) -> bool:
    try:
        row = _row(db, key)
    except Exception:  # unreadable: take the fallback, never the model
        return True
    return row is not None and row.state == "open"


def _day(moment: datetime) -> str:
    return f"{moment:%b} {moment.day}"


def breaker_message(db: Session, key: str) -> str | None:
    name = MODELS[key].name
    try:
        row = _row(db, key)
    except Exception:
        return f"{name} is paused while its safety switch cannot be checked."
    if row is None or row.state != "open":
        return None
    return f"{name} is paused: {row.reason} Since {_day(row.changed_at)}."


def ensure_closed(db: Session, key: str) -> None:
    message = breaker_message(db, key)
    if message:
        raise BreakerOpen(key, message)


def _change(db: Session, key: str, state: str, reason: str, by: str, now: datetime,
            run_id: str | None) -> ModelBreaker:
    row = db.get(ModelBreaker, key)
    if row is None:
        row = ModelBreaker(model_key=key, state="closed", reason="", changed_by="", changed_at=now, history=[])
        db.add(row)
    row.state, row.reason, row.changed_by, row.changed_at, row.run_id = state, reason, by, now, run_id
    row.history = [*(row.history or []), {"state": state, "reason": reason, "by": by, "at": now.isoformat(),
                                          "run_id": run_id}]
    db.flush()
    purpose = "breaker_open" if state == "open" else "breaker_reset"
    record_decision(db, agent="governance", purpose=purpose,
                    result=LLMResult(parsed={"model": key, "state": state, "reason": reason, "by": by,
                                             "run_id": run_id},
                                     model="rules", tokens_in=0, tokens_out=0, latency_ms=0, cost_usd=0.0),
                    subject_type="model", subject_id=key, input_text=reason)
    emit("BreakerOpened" if state == "open" else "BreakerReset", {"model": key, "by": by, "run_id": run_id})
    return row


def _checked(key: str, reason: str) -> str:
    if key not in MODELS:
        raise BreakerError(f"Atrium has no model called {key}.")
    reason = (reason or "").strip()
    if not reason:
        raise BreakerError("Give a reason; it is kept in the model's history.")
    return reason


def trip(db: Session, key: str, *, reason: str, by: str, now: datetime | None = None,
         run_id: str | None = None, by_id: str | None = None) -> ModelBreaker:
    """Open a breaker. An already open breaker keeps its first reason. `by_id` is the person who paused it by hand,
    whom the inbox does not tell about it."""
    reason = _checked(key, reason)
    row = db.get(ModelBreaker, key)
    if row is not None and row.state == "open":
        return row
    row = _change(db, key, "open", reason, by, now or utcnow(), run_id)
    notices.model_paused(db, row, besides=by_id)
    return row


def reset(db: Session, key: str, *, reason: str, person: Person, code: str,
          now: datetime | None = None) -> ModelBreaker:
    reason = _checked(key, reason)
    now = now or utcnow()
    row = db.get(ModelBreaker, key)
    if row is None or row.state != "open":
        raise BreakerError(f"{MODELS[key].name} is not paused.")
    if not verify_code(person, code, now):
        raise BreakerError("That code is not right. Use the current code from your authenticator.")
    return _change(db, key, "closed", reason, person.full_name, now, None)
