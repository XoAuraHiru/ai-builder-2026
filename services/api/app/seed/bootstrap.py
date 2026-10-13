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
from app.seed.migrate import apply_migrations

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
            apply_migrations(db.connection())  # new columns on tables an earlier release created
            if not settings.auto_seed:
                db.commit()
                return "disabled"
            from app.seed.leads import seed_demo_leads  # light: models only

            if is_seeded(db):
                if seed_demo_leads(db):  # databases seeded before leads existed get them once
                    log.info("seeded demo leads")
                from app.seed.trading import seed_trading

                if seed_trading(db):  # databases seeded before trading existed get it once
                    log.info("seeded paper-trading data")
                from app.seed.operations import seed_operations

                if seed_operations(db):  # databases seeded before operations existed get it once
                    log.info("seeded operations data")
                from app.seed.calls import seed_call_stories
                from app.seed.rings import seed_ring_link

                if seed_call_stories(db):  # databases seeded before call intelligence get its lead once
                    log.info("seeded call stories")
                if seed_ring_link(db):  # and the link that joins the lead ring to a client account
                    log.info("seeded the ring link")
                db.commit()
                return "skipped"
            import app.seed.generate as gen

            report = gen.generate(db, settings)
            seed_demo_leads(db)
            from app.seed.trading import seed_trading

            seed_trading(db)
            from app.seed.operations import seed_operations

            if seed_operations(db):
                log.info("seeded operations data")
            from app.seed.calls import seed_call_stories
            from app.seed.rings import seed_ring_link

            if seed_call_stories(db):  # databases seeded before call intelligence get its lead once
                log.info("seeded call stories")
            if seed_ring_link(db):  # and the link that joins the lead ring to a client account
                log.info("seeded the ring link")
            db.commit()
            log.info("seeded database: %s", report)
            return "seeded"
        except (IntegrityError, ProgrammingError) as e:
            db.rollback()
            log.warning("database bootstrap collided with another instance; continuing without seeding: %s", e)
            return "failed"
