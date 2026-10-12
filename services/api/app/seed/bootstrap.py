"""Create tables and seed once, safely when several Cloud Run instances start against an empty database.

Runs on every cold start, so the already-seeded path stays light: the generator, pandas-heavy pricing
and yfinance are imported only when the database is actually empty.
"""
import logging

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import Base, SessionLocal

log = logging.getLogger(__name__)

# Any constant shared by every instance; Postgres serialises holders of the same advisory lock key.
BOOTSTRAP_LOCK_KEY = 7_202_610


def is_seeded(db: Session) -> bool:
    from app.models import Person

    return (db.scalar(select(func.count()).select_from(Person)) or 0) > 0


def bootstrap_database(settings: Settings) -> str:
    """Returns "seeded", "skipped" (already seeded), "disabled" (auto_seed off) or "failed" (collided; logged)."""
    import app.models  # noqa: F401  registers every table on Base.metadata

    with SessionLocal() as db:
        try:
            if db.get_bind().dialect.name == "postgresql":
                # Held until commit/rollback: a second instance waits here, then finds the data and skips.
                db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": BOOTSTRAP_LOCK_KEY})
            Base.metadata.create_all(bind=db.connection())
            if not settings.auto_seed:
                db.commit()
                return "disabled"
            if is_seeded(db):
                db.commit()
                return "skipped"
            import app.seed.generate as gen

            report = gen.generate(db, settings)
            db.commit()
            log.info("seeded database: %s", report)
            return "seeded"
        except (IntegrityError, ProgrammingError) as e:
            db.rollback()
            log.warning("database bootstrap collided with another instance; continuing without seeding: %s", e)
            return "failed"
