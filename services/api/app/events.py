"""Domain events. Services call `emit`; agents in later plans subscribe by event type.

Event types in use: PricePublished {fund_code, as_of, nav}. Later plans add LeadCreated, TrustScoreChanged,
InstructionReceived, OrderPlaced, OrderFilled, TransactionPosted, StatementUploaded, MatchProposed,
AlertRaised and CaseDecided (blueprint section 9).
"""
from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.config import Settings
from app.models.base import new_id, utcnow

Handler = Callable[["Event"], None]


@dataclass
class Event:
    type: str
    payload: dict
    id: str = field(default_factory=new_id)
    occurred_at: datetime = field(default_factory=utcnow)

    def to_json(self) -> str:
        return json.dumps(
            {"id": self.id, "type": self.type, "occurred_at": self.occurred_at.isoformat(), "payload": self.payload},
            default=str,
        )


class EventBus(Protocol):
    def publish(self, event: Event) -> None: ...
    def subscribe(self, event_type: str, handler: Handler) -> None: ...


class InProcessEventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self.history: list[Event] = []

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: Event) -> None:
        self.history.append(event)
        for handler in list(self._handlers.get(event.type, [])):
            handler(event)


def _make_publisher():
    from google.cloud import pubsub_v1

    return pubsub_v1.PublisherClient()


class PubSubEventBus:
    """Publishes every event to one Pub/Sub topic (attribute `type`) and dispatches locally too."""

    def __init__(self, project: str, topic: str, inner: InProcessEventBus | None = None) -> None:
        # The gRPC client is created on first publish, not here: building it at startup would add to every
        # scale-from-zero cold start, and most requests never publish.
        self._publisher = None
        self._topic_path = f"projects/{project}/topics/{topic}"
        self._inner = inner or InProcessEventBus()

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._inner.subscribe(event_type, handler)

    def publish(self, event: Event) -> None:
        if self._publisher is None:
            self._publisher = _make_publisher()
        # Fire and forget: the client batches and retries; blocking here would stall seeding (thousands of events).
        self._publisher.publish(self._topic_path, event.to_json().encode("utf-8"), type=event.type)
        self._inner.publish(event)


_bus: EventBus | None = None


def set_event_bus(bus: EventBus) -> None:
    global _bus
    _bus = bus


def current_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = InProcessEventBus()
    return _bus


def get_event_bus(settings: Settings) -> EventBus:
    if settings.pubsub_enabled:
        if not settings.gcp_project:
            raise ValueError("GCP_PROJECT is required when PUBSUB_ENABLED=true")
        return PubSubEventBus(settings.gcp_project, settings.pubsub_topic)
    return InProcessEventBus()


def emit(event_type: str, payload: dict) -> Event:
    event = Event(type=event_type, payload=payload)
    current_bus().publish(event)
    return event
