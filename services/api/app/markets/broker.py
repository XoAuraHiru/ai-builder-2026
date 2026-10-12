"""Where orders go (C2). Atrium's own paper broker fills orders against the quote. The Alpaca adapter sends them to
Alpaca's paper-trading API instead and is used only when ALPACA_API_KEY and ALPACA_SECRET_KEY are both set."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.config import get_settings
from app.markets.quotes import Quote, with_spread

ALPACA_OPEN = {"new", "accepted", "pending_new", "partially_filled", "accepted_for_bidding", "pending_replace",
               "held", "calculated", "replaced", "done_for_day"}


@dataclass(frozen=True)
class BrokerOrder:
    symbol: str
    side: str
    order_type: str
    quantity: int
    limit_price: Decimal | None
    kind: str             # stock | etf, for the spread estimate
    client_order_id: str  # Atrium's order id


@dataclass(frozen=True)
class Execution:
    status: str           # filled | open | rejected
    price: Decimal | None
    broker_order_id: str
    note: str


class Broker(Protocol):
    name: str

    def submit(self, order: BrokerOrder, quote: Quote, market_open: bool) -> Execution: ...

    def check(self, order: BrokerOrder, broker_order_id: str, quote: Quote) -> Execution: ...

    def cancel(self, broker_order_id: str) -> None: ...


class PaperBroker:
    """Fills a market order at once, at the quote and half the estimated spread; a limit order when the quote reaches
    it. While the market is closed, a market order fills at the last close, and the note says so."""

    name = "atrium-paper"

    def submit(self, order: BrokerOrder, quote: Quote, market_open: bool) -> Execution:
        broker_order_id = f"paper-{order.client_order_id}"
        if order.order_type == "limit":
            return self.check(order, broker_order_id, quote)
        price = with_spread(order.side, order.kind, quote.price)
        when = "at the current price" if market_open else "at the last close, because the market is closed"
        return Execution("filled", price, broker_order_id, f"Filled in paper trading {when}: ${price:,.2f} a share.")

    def check(self, order: BrokerOrder, broker_order_id: str, quote: Quote) -> Execution:
        limit = Decimal(order.limit_price)
        if order.side == "buy" and quote.price <= limit:
            price = min(limit, with_spread("buy", order.kind, quote.price))
        elif order.side == "sell" and quote.price >= limit:
            price = max(limit, with_spread("sell", order.kind, quote.price))
        else:
            return Execution("open", None, broker_order_id,
                             f"Waiting: the price is ${quote.price:,.2f}, and your limit is ${limit:,.2f}.")
        return Execution("filled", price, broker_order_id,
                         f"Filled in paper trading at ${price:,.2f} a share; the price reached your limit.")

    def cancel(self, broker_order_id: str) -> None:
        return None


class AlpacaPaperBroker:
    name = "alpaca-paper"

    def __init__(self, client):
        self._client = client

    @classmethod
    def from_keys(cls, api_key: str, secret_key: str) -> "AlpacaPaperBroker":
        from alpaca.trading.client import TradingClient

        return cls(TradingClient(api_key, secret_key, paper=True))

    def submit(self, order: BrokerOrder, quote: Quote, market_open: bool) -> Execution:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

        common = dict(symbol=order.symbol, qty=order.quantity, time_in_force=TimeInForce.DAY,
                      side=OrderSide.BUY if order.side == "buy" else OrderSide.SELL,
                      client_order_id=order.client_order_id)
        request = (MarketOrderRequest(**common) if order.order_type == "market"
                   else LimitOrderRequest(limit_price=float(order.limit_price), **common))
        return self._execution(self._client.submit_order(order_data=request))

    def check(self, order: BrokerOrder, broker_order_id: str, quote: Quote) -> Execution:
        return self._execution(self._client.get_order_by_id(broker_order_id))

    def cancel(self, broker_order_id: str) -> None:
        self._client.cancel_order_by_id(broker_order_id)

    @staticmethod
    def _execution(o) -> Execution:
        status = str(getattr(o.status, "value", o.status))
        words = status.replace("_", " ")
        if status == "filled":
            price = Decimal(str(o.filled_avg_price))
            return Execution("filled", price, str(o.id), f"Filled by Alpaca paper trading at ${price:,.2f} a share.")
        if status in ALPACA_OPEN:
            return Execution("open", None, str(o.id), f"Sent to Alpaca paper trading; its status is {words}.")
        return Execution("rejected", None, str(o.id), f"Alpaca paper trading did not fill the order: {words}.")


def get_broker() -> Broker:
    settings = get_settings()
    if settings.alpaca_api_key and settings.alpaca_secret_key:
        return AlpacaPaperBroker.from_keys(settings.alpaca_api_key, settings.alpaca_secret_key)
    return PaperBroker()


def broker_dep() -> Broker:
    """FastAPI dependency; tests override it."""
    return get_broker()
