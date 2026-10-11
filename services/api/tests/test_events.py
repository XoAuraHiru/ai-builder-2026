import json
from decimal import Decimal

import pandas as pd

from app.config import Settings
from app.events import Event, InProcessEventBus, PubSubEventBus, current_bus, get_event_bus, set_event_bus
from app.seed.funds import seed_funds
from app.services.pricing import publish_prices


def test_in_process_bus_dispatches_to_subscribers_and_records_history():
    bus = InProcessEventBus()
    seen = []
    bus.subscribe("PricePublished", seen.append)

    def wrong_handler(event):
        raise AssertionError("wrong handler called")

    bus.subscribe("Other", wrong_handler)
    ev = Event(type="PricePublished", payload={"fund_code": "ATR-BAL"})
    bus.publish(ev)
    assert seen == [ev] and bus.history == [ev]
    assert json.loads(ev.to_json())["payload"]["fund_code"] == "ATR-BAL"
    assert len(ev.id) == 32


def test_publish_prices_emits_one_event_per_date(db):
    bus = InProcessEventBus()
    set_event_bus(bus)
    seed_funds(db)
    nav = pd.Series([100.0, 101.0], index=pd.to_datetime(["2026-01-02", "2026-01-05"]))
    publish_prices(db, "ATR-BAL", nav, Decimal("1000000"))
    types = [e.type for e in bus.history]
    assert types == ["PricePublished", "PricePublished"]
    assert bus.history[1].payload == {"fund_code": "ATR-BAL", "as_of": "2026-01-05", "nav": "101.000000"}


def test_get_event_bus_returns_in_process_when_pubsub_disabled():
    bus = get_event_bus(Settings(_env_file=None, pubsub_enabled=False))
    assert isinstance(bus, InProcessEventBus)


def test_pubsub_bus_publishes_json_with_type_attribute(monkeypatch):
    sent = []

    class FakePublisher:
        def topic_path(self, project, topic):
            return f"projects/{project}/topics/{topic}"

        def publish(self, topic_path, data, **attrs):
            sent.append((topic_path, json.loads(data.decode()), attrs))

    import app.events as mod

    monkeypatch.setattr(mod, "_make_publisher", lambda: FakePublisher())
    inner = InProcessEventBus()
    bus = PubSubEventBus(project="atrium-cup-2026", topic="atrium-events", inner=inner)
    bus.publish(Event(type="PricePublished", payload={"fund_code": "ATR-TEC"}))
    assert sent[0][0] == "projects/atrium-cup-2026/topics/atrium-events"
    assert sent[0][1]["type"] == "PricePublished" and sent[0][2] == {"type": "PricePublished"}
    assert len(inner.history) == 1
    assert current_bus() is not None


def test_pubsub_client_is_created_on_first_publish_not_at_startup(monkeypatch):
    """The gRPC client is heavy; creating it at startup would lengthen every scale-from-zero cold start."""
    import app.events as mod

    created = []

    class FakePublisher:
        def publish(self, topic_path, data, **attrs):
            created.append(("publish", topic_path))

    def make():
        created.append("client")
        return FakePublisher()

    monkeypatch.setattr(mod, "_make_publisher", make)
    bus = PubSubEventBus(project="atrium-cup-2026", topic="atrium-events")
    assert created == []
    bus.publish(Event(type="PricePublished", payload={}))
    bus.publish(Event(type="PricePublished", payload={}))
    assert created == ["client", ("publish", "projects/atrium-cup-2026/topics/atrium-events"),
                       ("publish", "projects/atrium-cup-2026/topics/atrium-events")]
