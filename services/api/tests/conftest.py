import os

import pytest

# Test environment is fixed before any app module is imported.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("AUTH_MODE", "dev")
os.environ.setdefault("MARKET_DATA_PROVIDER", "fake")
os.environ.setdefault("PUBSUB_ENABLED", "false")
os.environ["AUTO_SEED"] = "false"  # never seed test databases, even if a local .env says otherwise


@pytest.fixture(autouse=True)
def _fresh_event_bus():
    """One test's subscribers never leak into the next."""
    from app.events import InProcessEventBus, set_event_bus

    set_event_bus(InProcessEventBus())
    yield
    set_event_bus(InProcessEventBus())


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


@pytest.fixture()
def people(db):
    from app.models import Person

    advisor = Person(kind="advisor", full_name="Daniel Okafor", email="daniel@atrium.demo")
    investor = Person(kind="investor", full_name="Priya Raman", email="priya@atrium.demo")
    db.add_all([advisor, investor])
    db.commit()
    return {"advisor": advisor, "investor": investor}


@pytest.fixture()
def make_lead(db):
    from decimal import Decimal

    from app.models import Lead

    def _make(**overrides):
        fields = dict(source="web", full_name="Ava Thompson", email="ava@example.test", phone="+14155550123",
                      country="US", goals="Grow savings for retirement in 20 years", horizon_years=20,
                      investable_usd=Decimal("60000"), monthly_usd=Decimal("500"), source_of_funds="salary",
                      notes=None, device_id="dev-ava-0001", ip_hash="ip-test")
        fields.update(overrides)
        lead = Lead(**fields)
        db.add(lead)
        db.commit()
        return lead

    return _make


@pytest.fixture()
def client(db):
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
