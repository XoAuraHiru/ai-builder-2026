"""Create tables and seed once, safely when several Cloud Run instances start against an empty database."""
import logging

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError

import app.seed.generate as gen
from app.config import Settings
from app.db import Base, SessionLocal

log = logging.getLogger(__name__)

# Any constant shared by every instance; Postgres serialises holders of the same advisory lock key.
BOOTSTRAP_LOCK_KEY = 7_202_610


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
            if gen.is_seeded(db):
                db.commit()
                return "skipped"
            report = gen.generate(db, settings)
            db.commit()
            log.info("seeded database: %s", report)
            return "seeded"
        except (IntegrityError, ProgrammingError) as e:
            db.rollback()
            log.warning("database bootstrap collided with another instance; continuing without seeding: %s", e)
            return "failed"
