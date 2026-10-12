from datetime import date, datetime, timezone
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import select

from app.events import current_bus
from app.markets.broker import PaperBroker
from app.markets.quotes import CommittedQuotes
from app.markets.universe import CASH
from app.models import AccountDevice, Person, Posting
from app.services.guardian import OrderRequest
from app.services.ledger import balance
from app.services.orders import (ACKNOWLEDGE, OrderError, cancel_order, place_order, preview_order, refresh_orders,
                                 reject_order, release_order)

NOW = datetime(2026, 10, 9, 15, tzinfo=timezone.utc)  # Friday, 11:00 in New York: the market is open
DAILY = pd.DataFrame({"KO": [60.0, 61.0], "TSLA": [400.0, 400.0]},
                     index=pd.to_datetime(["2026-10-08", "2026-10-09"]))
BOOK = CommittedQuotes(DAILY)


def buy(symbol, qty, order_type="market", limit=None):
    return OrderRequest(symbol, "buy", order_type, qty, Decimal(limit) if limit else None)


def place(db, account, req, **kw):
    return place_order(db, account, req, now=kw.pop("now", NOW), quotes=kw.pop("quotes", BOOK),
                       broker=PaperBroker(), device_hash=kw.pop("device_hash", "dev-1"), **kw)


@pytest.fixture()
def investor(db, account, paper):
    paper.deposit(account, "10000")
    db.get(Person, account.person_id).risk_band = 5
    db.commit()
    return account


@pytest.fixture()
def advisor(db):
    person = Person(kind="advisor", full_name="Daniel Okafor", email="daniel@atrium.demo")
    db.add(person)
    db.commit()
    return person


def events():
    return [e.type for e in current_bus().history]


def test_a_clean_market_buy_fills_and_posts_shares_and_cash(db, investor):
    order = place(db, investor, buy("KO", 3), device_label="Chrome on Windows")
    assert (order.state, order.verdict, order.fill_price) == ("filled", "proceed", Decimal("61.0122"))
    assert [s["state"] for s in order.timeline] == ["placed", "filled"]
    assert balance(db, investor.id, "KO") == Decimal("3") and balance(db, investor.id, CASH) == Decimal("9816.96")
    refs = db.scalars(select(Posting.reference).where(Posting.account_id == investor.id,
                                                      Posting.posting_type == "buy")).all()
    assert refs == [order.id, order.id]
    assert {"OrderPlaced", "OrderFilled", "TransactionPosted"} <= set(events())
    assert db.scalar(select(AccountDevice.label)) == "Chrome on Windows"
    assert order.guardian["verdict"] == "proceed" and order.trust_score == 90  # first use of this browser


def test_warnings_must_be_acknowledged(db, investor):
    db.get(Person, investor.person_id).risk_band = 4
    with pytest.raises(OrderError, match=ACKNOWLEDGE):
        place(db, investor, buy("TSLA", 3))
    order = place(db, investor, buy("TSLA", 3), acknowledge=True)
    assert order.state == "filled" and order.acknowledged_warnings is True


def test_a_held_order_waits_for_an_advisor_who_can_release_it(db, investor, advisor):
    db.get(Person, investor.person_id).risk_band = 2
    order = place(db, investor, buy("TSLA", 3))
    assert (order.state, order.verdict) == ("held", "hold")
    assert balance(db, investor.id, "TSLA") == Decimal("0") and "OrderHeld" in events()
    assert preview_order(db, investor, buy("KO", 1), now=NOW, quotes=BOOK).estimate.cash_after < Decimal("8800")
    release_order(db, order, advisor, "Spoke with the client; they understand the risk.", now=NOW, quotes=BOOK,
                  broker=PaperBroker())
    assert order.state == "filled" and order.reviewed_by == advisor.id
    assert [s["state"] for s in order.timeline] == ["placed", "held", "released", "filled"]
    assert "Daniel Okafor" in order.timeline[2]["note"]


def test_an_advisor_can_reject_a_held_order(db, investor, advisor):
    db.get(Person, investor.person_id).risk_band = 2
    order = place(db, investor, buy("TSLA", 3))
    reject_order(db, order, advisor, "Outside the client's profile.", now=NOW)
    assert order.state == "rejected" and order.review_note == "Outside the client's profile."
    with pytest.raises(OrderError):
        release_order(db, order, advisor, now=NOW, quotes=BOOK, broker=PaperBroker())


def test_release_refuses_when_the_cash_has_gone(db, account, paper, advisor):
    paper.deposit(account, "1000")
    db.get(Person, account.person_id).risk_band = 2
    order = place(db, account, buy("TSLA", 2))
    assert order.state == "held"
    paper.trade(account, "buy", "KO", 10, "61", day=date(2026, 10, 9))  # the cash is spent elsewhere
    with pytest.raises(OrderError, match="can no longer go ahead"):
        release_order(db, order, advisor, now=NOW, quotes=BOOK, broker=PaperBroker())
    assert order.state == "held"


def test_a_limit_order_rests_reserves_cash_and_fills_when_the_price_comes(db, investor):
    order = place(db, investor, buy("KO", 10, "limit", "55"))
    assert order.state == "open" and [s["state"] for s in order.timeline] == ["placed", "open"]
    assert preview_order(db, investor, buy("KO", 1), now=NOW, quotes=BOOK).estimate.cash_after < Decimal("9500")
    assert refresh_orders(db, investor.id, now=NOW, quotes=BOOK, broker=PaperBroker()) == 0
    cheaper = CommittedQuotes(pd.DataFrame({"KO": [61.0, 54.0]}, index=pd.to_datetime(["2026-10-08", "2026-10-09"])))
    assert refresh_orders(db, investor.id, now=NOW, quotes=cheaper, broker=PaperBroker()) == 1
    assert order.state == "filled" and order.fill_price == Decimal("54.0108")


def test_waiting_orders_can_be_cancelled_and_finished_ones_cannot(db, investor):
    order = place(db, investor, buy("KO", 10, "limit", "55"))
    cancel_order(db, order, now=NOW, broker=PaperBroker())
    assert order.state == "cancelled" and order.timeline[-1]["state"] == "cancelled"
    filled = place(db, investor, buy("KO", 1))
    with pytest.raises(OrderError):
        cancel_order(db, filled, now=NOW, broker=PaperBroker())


def test_a_blocked_order_is_refused_with_its_reason(db, investor):
    with pytest.raises(OrderError, match="needs about"):
        place(db, investor, buy("TSLA", 100))
    with pytest.raises(OrderError, match="not in Atrium's trading list"):
        place(db, investor, buy("ZZZZ", 1))


def test_selling_returns_paper_cash(db, investor):
    place(db, investor, buy("KO", 5))
    # Selling straight back at a small loss within 30 days of buying is a wash-sale warning: it must be confirmed.
    with pytest.raises(OrderError, match=ACKNOWLEDGE):
        place(db, investor, OrderRequest("KO", "sell", "market", 5))
    sale = place(db, investor, OrderRequest("KO", "sell", "market", 5), acknowledge=True)
    assert sale.state == "filled" and balance(db, investor.id, "KO") == Decimal("0")
    assert balance(db, investor.id, CASH) == Decimal("9999.88")  # 10,000 - 305.06 + 304.94


def test_order_work_takes_a_postgres_advisory_lock_per_account():
    from types import SimpleNamespace

    from app.services.orders import lock_account

    executed = []

    class FakeDb:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def execute(self, statement, params=None):
            executed.append((str(statement), params))

    lock_account(FakeDb(), "acc-1")
    assert executed == [("SELECT pg_advisory_xact_lock(hashtext(:key))", {"key": "account:acc-1"})]


def test_every_order_action_locks_the_account_first(db, investor, advisor, monkeypatch):
    import app.services.orders as orders

    seen = []
    monkeypatch.setattr(orders, "lock_account", lambda session, account_id: seen.append(account_id))
    resting = place(db, investor, buy("KO", 10, "limit", "55"))
    refresh_orders(db, investor.id, now=NOW, quotes=BOOK, broker=PaperBroker())
    cancel_order(db, resting, now=NOW, broker=PaperBroker())
    db.get(Person, investor.person_id).risk_band = 2
    held = place(db, investor, buy("TSLA", 3))
    reject_order(db, held, advisor, now=NOW)
    again = place(db, investor, buy("TSLA", 3))
    release_order(db, again, advisor, now=NOW, quotes=BOOK, broker=PaperBroker())
    assert seen == [investor.id] * 7


def test_release_rereads_the_order_after_taking_the_lock(db, investor, advisor):
    from sqlalchemy import update

    from app.models import TradeOrder

    db.get(Person, investor.person_id).risk_band = 2
    order = place(db, investor, buy("TSLA", 3))
    # Another request rejected it after this one loaded the order.
    db.execute(update(TradeOrder).where(TradeOrder.id == order.id).values(state="rejected")
               .execution_options(synchronize_session=False))
    with pytest.raises(OrderError, match="Only an order waiting"):
        release_order(db, order, advisor, now=NOW, quotes=BOOK, broker=PaperBroker())
