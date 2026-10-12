from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.markets.broker import AlpacaPaperBroker, BrokerOrder, PaperBroker
from app.markets.quotes import Quote

NOW = datetime(2026, 10, 12, 15, tzinfo=timezone.utc)


def order(side="buy", order_type="market", limit=None):
    return BrokerOrder("KO", side, order_type, 10, Decimal(limit) if limit else None, "stock", "o1")


def quote(price):
    return Quote("KO", Decimal(price), Decimal(price), NOW, "live")


def test_paper_market_orders_fill_at_once_with_half_the_spread():
    filled = PaperBroker().submit(order(), quote("60"), market_open=True)
    assert (filled.status, filled.price, filled.broker_order_id) == ("filled", Decimal("60.0120"), "paper-o1")
    closed = PaperBroker().submit(order(side="sell"), quote("60"), market_open=False)
    assert closed.price == Decimal("59.9880") and "market is closed" in closed.note


def test_paper_limit_orders_wait_for_their_price():
    broker = PaperBroker()
    waiting = broker.submit(order(order_type="limit", limit="55"), quote("60"), market_open=True)
    assert waiting.status == "open" and "your limit is $55.00" in waiting.note
    filled = broker.check(order(order_type="limit", limit="55"), "paper-o1", quote("54"))
    assert filled.status == "filled" and filled.price == Decimal("54.0108")
    capped = broker.check(order(order_type="limit", limit="55"), "paper-o1", quote("54.999"))
    assert capped.price == Decimal("55")


class FakeAlpaca:
    def __init__(self, status, price=None):
        self.submitted, self.cancelled = [], []
        self.reply = SimpleNamespace(id="alp-1", status=SimpleNamespace(value=status), filled_avg_price=price)

    def submit_order(self, order_data):
        self.submitted.append(order_data)
        return self.reply

    def get_order_by_id(self, order_id):
        return self.reply

    def cancel_order_by_id(self, order_id):
        self.cancelled.append(order_id)


def test_alpaca_adapter_sends_the_order_and_reads_its_status():
    client = FakeAlpaca("accepted")
    broker = AlpacaPaperBroker(client)
    sent = broker.submit(order(order_type="limit", limit="55"), quote("60"), market_open=True)
    request = client.submitted[0]
    assert (request.symbol, request.qty, request.limit_price, request.client_order_id) == ("KO", 10, 55.0, "o1")
    assert sent.status == "open" and sent.broker_order_id == "alp-1"
    client.reply.status, client.reply.filled_avg_price = SimpleNamespace(value="filled"), "54.98"
    assert broker.check(order(), "alp-1", quote("54")).price == Decimal("54.98")
    client.reply.status = SimpleNamespace(value="rejected")
    assert broker.check(order(), "alp-1", quote("54")).status == "rejected"
    broker.cancel("alp-1")
    assert client.cancelled == ["alp-1"]
