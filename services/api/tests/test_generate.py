from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.config import Settings
from app.models import Account, Instruction, Person, Posting, Price
from app.seed.generate import PERSONAS, generate, is_seeded
from app.services.ledger import balance, holdings
from app.services.pricing import pricing_guard


def settings():
    return Settings(_env_file=None, market_data_provider="fake", seed=42)


def test_generate_populates_every_table_deterministically(db):
    assert is_seeded(db) is False
    report = generate(db, settings(), end=date(2026, 10, 9))
    db.commit()
    assert is_seeded(db) is True
    assert report.people == len(PERSONAS) == 12
    assert report.accounts == 9  # three staff personas have no account
    assert report.instructions == report.postings > 100
    assert db.scalar(select(Person).where(Person.email == "priya@atrium.demo")).kind == "investor"
    assert db.scalar(select(Person).where(Person.email == "daniel@atrium.demo")).kind == "advisor"
    assert db.scalar(select(Person).where(Person.email == "mei@atrium.demo")).kind == "ops"
    # every investor holds something and nothing is negative
    for acc in db.scalars(select(Account)).all():
        hs = holdings(db, acc.id)
        assert hs, f"{acc.number} has no holdings"
        for h in hs:
            assert balance(db, acc.id, h.instrument) >= 0
    # every instruction is settled and every posting references one
    instructions = db.scalars(select(Instruction)).all()
    assert all(i.state == "settled" for i in instructions)
    refs = {p.reference for p in db.scalars(select(Posting)).all()}
    assert all(i.id in refs for i in instructions)
    # prices exist for all seven funds on the last business day
    assert report.last_price_date == date(2026, 10, 9)
    assert pricing_guard(db, report.last_price_date) == []

    def fingerprint():
        return sorted(
            (p.instrument, p.value_date, p.posting_type, p.units, p.cash)
            for p in db.scalars(select(Posting)).all()
        )

    first = fingerprint()
    # determinism: a second run on a fresh schema yields identical postings (ids differ, facts do not)
    from app.db import Base, engine

    db.expunge_all()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    generate(db, settings(), end=date(2026, 10, 9))
    db.commit()
    assert fingerprint() == first


def test_units_equal_net_amount_over_nav(db):
    generate(db, settings(), end=date(2026, 10, 9))
    db.commit()
    posting = db.scalar(select(Posting).where(Posting.posting_type == "subscription").limit(1))
    price = db.scalar(select(Price).where(Price.fund_code == posting.instrument, Price.as_of == posting.value_date))
    assert price is not None
    assert posting.units == (-posting.cash / price.nav).quantize(Decimal("0.000001"))


def test_generate_falls_back_to_price_snapshot_when_provider_fails(db, monkeypatch):
    import app.seed.generate as gen
    from app.services.market_data import MarketDataError

    class Blocked:
        def history(self, tickers, start, end):
            raise MarketDataError("simulated: Yahoo blocked this IP")

    monkeypatch.setattr(gen, "get_market_data", lambda settings: Blocked())
    report = generate(db, Settings(_env_file=None, market_data_provider="yfinance", seed=42), end=date(2026, 10, 9))
    db.commit()
    assert report.price_source == "snapshot"
    assert report.prices > 3000 and report.last_price_date >= date(2026, 10, 1)
    assert pricing_guard(db, report.last_price_date) == []
