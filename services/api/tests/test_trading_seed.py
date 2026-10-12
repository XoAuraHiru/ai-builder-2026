from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.markets.universe import CASH
from app.models import Account, AccountDevice, Person, Posting, TradeOrder
from app.seed.trading import seed_trading
from app.services.ledger import balance, holdings

TODAY = date(2026, 10, 9)


@pytest.fixture()
def demo_accounts(db):
    out = {}
    for i, email in enumerate(["priya@atrium.demo", "lucas@atrium.demo", "tom@atrium.demo", "hana@atrium.demo",
                               "jose@example.test"], start=1):
        person = Person(kind="investor", full_name=email.split("@")[0].title(), email=email, country="US", risk_band=4)
        db.add(person)
        db.flush()
        account = Account(person_id=person.id, number=f"ACC-{i:04d}", opened_on=date(2024, 10, 1))
        db.add(account)
        db.flush()
        out[email.split("@")[0]] = account
    db.add(Person(kind="advisor", full_name="Daniel Okafor", email="daniel@atrium.demo"))
    db.commit()
    return out


def test_seed_gives_cash_positions_devices_and_the_loss_story(db, demo_accounts):
    assert seed_trading(db, today=TODAY) is True
    lucas, tom, hana = demo_accounts["lucas"], demo_accounts["tom"], demo_accounts["hana"]
    assert balance(db, lucas.id, CASH) == Decimal("15000")  # paper cash left after the seeded positions
    assert {h.instrument for h in holdings(db, lucas.id)} == {CASH, "NVDA", "AAPL", "MSFT"}
    assert balance(db, tom.id, "TSLA") == Decimal("120")
    assert balance(db, demo_accounts["priya"].id, CASH) == Decimal("20000")
    assert balance(db, demo_accounts["jose"].id, CASH) == Decimal("10000")  # any other investor gets the default
    sale = db.scalar(select(Posting).where(Posting.account_id == hana.id, Posting.posting_type == "sell"))
    assert sale is not None and sale.cash < sale.realised_cost and 8 <= (TODAY - sale.value_date).days <= 20
    assert db.scalar(select(func.count()).select_from(AccountDevice)) == 5
    orders = db.scalars(select(TradeOrder).where(TradeOrder.account_id == lucas.id)).all()
    assert len(orders) == 3 and {o.state for o in orders} == {"filled"} and all(o.timeline for o in orders)


def test_seed_runs_once(db, demo_accounts):
    assert seed_trading(db, today=TODAY) is True
    assert seed_trading(db, today=TODAY) is False


def test_seed_without_investors_does_nothing(db):
    assert seed_trading(db, today=TODAY) is False
