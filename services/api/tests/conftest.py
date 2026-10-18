import os

import pytest

# Test environment is fixed before any app module is imported.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("AUTH_MODE", "dev")
os.environ.setdefault("MARKET_DATA_PROVIDER", "fake")
os.environ.setdefault("PUBSUB_ENABLED", "false")
os.environ["AUTO_SEED"] = "false"  # never seed test databases, even if a local .env says otherwise
os.environ["FIRESTORE_ENABLED"] = "false"  # never write to Firestore from tests; the `inbox` fixture records instead


@pytest.fixture(autouse=True)
def _fresh_event_bus():
    """One test's subscribers never leak into the next."""
    from app.events import InProcessEventBus, set_event_bus

    set_event_bus(InProcessEventBus())
    yield
    set_event_bus(InProcessEventBus())


@pytest.fixture(autouse=True)
def _inbox_off():
    """The live inbox is off unless a test asks for the `inbox` recorder, and one test's never leaks into the next."""
    from app.realtime.inbox import set_courier

    set_courier(None)
    yield
    set_courier(None)


class InboxRecorder:
    """What the live inbox delivered, written synchronously as each transaction commits."""

    def __init__(self):
        self.sent = []

    def write(self, deliveries):
        self.sent.extend(deliveries)

    def to(self, person) -> list:
        """The items one person received (a Person or an id), in order."""
        person_id = getattr(person, "id", person)
        return [d.item for d in self.sent if d.person_id == person_id]

    def kinds(self) -> list[str]:
        return [d.item.kind for d in self.sent]


@pytest.fixture()
def inbox():
    from app.realtime.inbox import Courier, set_courier

    recorder = InboxRecorder()
    set_courier(Courier(recorder, background=False))
    return recorder


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


@pytest.fixture()
def paper(db):
    """Paper-trading ledger helpers: a cash deposit, and a filled share trade posted the way the order service posts it
    (the shares with their cash leg, then the paper cash that paid for them)."""
    from datetime import date
    from decimal import Decimal

    from app.services.ledger import apply_posting

    class Paper:
        @staticmethod
        def deposit(account, amount, day=date(2026, 10, 1)):
            apply_posting(db, account_id=account.id, instrument="USD", instrument_type="cash", posting_type="deposit",
                          units=Decimal(amount), cash=Decimal(amount), price=Decimal("1"), value_date=day,
                          reference="PAPER-CASH")

        @staticmethod
        def trade(account, side, symbol, qty, price, day=date(2026, 10, 2)):
            sign = 1 if side == "buy" else -1
            gross = Decimal(str(qty)) * Decimal(str(price))
            ref = f"T-{side}-{symbol}-{day}"
            apply_posting(db, account_id=account.id, instrument=symbol, instrument_type="equity", posting_type=side,
                          units=Decimal(sign * int(qty)), cash=-sign * gross, price=Decimal(str(price)),
                          value_date=day, reference=ref)
            apply_posting(db, account_id=account.id, instrument="USD", instrument_type="cash", posting_type=side,
                          units=-sign * gross, cash=Decimal("0"), price=Decimal("1"), value_date=day, reference=ref)

    return Paper()


@pytest.fixture()
def staff(db):
    """Two operations people (the maker and the checker of four-eyes approvals) and a compliance officer, each with a
    fixed authenticator secret so tests can compute their one-time codes."""
    from app.models import Person

    out = {}
    for key, kind, name, email, secret in (
            ("mei", "ops", "Mei Tanaka", "mei@atrium.demo", "JBSWY3DPEHPK3PXP"),
            ("sam", "ops", "Sam Ortiz", "sam@atrium.demo", "KRSXG5CTMVRXEZLU"),
            ("omar", "compliance", "Omar Haddad", "omar@atrium.demo", "MFRGGZDFMZTWQ2LK")):
        person = Person(kind=kind, full_name=name, email=email, totp_secret=secret)
        db.add(person)
        out[key] = person
    db.commit()
    return out
