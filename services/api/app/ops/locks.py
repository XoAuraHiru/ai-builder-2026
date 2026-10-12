"""One lock for operations work that moves instructions, statement lines or alerts.

The day-end (scheduled job or button), price publication, match decisions, "find matches" and monitoring each take it,
so they run one at a time: a match accepted while an allocation is dealing would otherwise leave a paid subscription
dealt but never settled. On Postgres it is a transaction-scoped advisory lock, released at commit or rollback; SQLite
(tests, local runs) has one writer anyway.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session


def serialise_operations(db: Session) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext('day-end'))"))
