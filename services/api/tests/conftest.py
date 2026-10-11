import os

import pytest

# Test environment is fixed before any app module is imported.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("AUTH_MODE", "dev")
os.environ.setdefault("MARKET_DATA_PROVIDER", "fake")
os.environ.setdefault("PUBSUB_ENABLED", "false")
os.environ["AUTO_SEED"] = "false"  # never seed test databases, even if a local .env says otherwise


@pytest.fixture()
def db():
    from app.db import Base, SessionLocal, engine, init_db

    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def account(db):
    from datetime import date

    from app.models import Account, Person

    person = Person(kind="investor", full_name="Priya Raman", email="priya@example.test", country="US")
    db.add(person)
    db.flush()
    acc = Account(person_id=person.id, number="ACC-0001", opened_on=date(2026, 1, 5))
    db.add(acc)
    db.commit()
    return acc
