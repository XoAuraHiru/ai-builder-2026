"""Inbox items, who receives them, and getting them to Firestore only once the work behind them is committed.

Notices stage items on the database session. When its outermost transaction commits, the items go to a courier that
writes them on a small thread pool; when it rolls back, or closes without committing, they are dropped, and a
savepoint that rolls back takes back what was staged inside it. Item ids are deterministic, so delivering the same
event twice rewrites one document instead of adding a second.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Iterable
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from itertools import batched
from typing import Protocol

from sqlalchemy import event, select
from sqlalchemy.orm import Session, SessionTransaction

from app.config import get_settings
from app.models import Person

log = logging.getLogger(__name__)

STAGES = ("acquire", "invest", "trade", "operate", "govern")
SEVERITIES = ("info", "attention", "urgent")
BATCH = 400  # Firestore takes at most 500 writes in one batch
WRITE_TIMEOUT = 8.0  # seconds; a slow Firestore costs a notice, never a hung request
_OUTBOX = "atrium.inbox"  # session.info key: [(the transaction that staged it, Delivery), ...]


@dataclass(frozen=True)
class Item:
    """One notice: what happened, in Atrium's words, and the page where a person acts on it."""

    kind: str           # order_held, approval_requested, ...
    source_id: str      # what it is about; with the kind, it names the document
    stage: str          # acquire | invest | trade | operate | govern
    title: str
    body: str
    href: str           # an app route
    severity: str       # info | attention | urgent
    actor: str          # who or what caused it: a person's name, "Pre-trade Guardian", "Day-end"

    def __post_init__(self) -> None:
        if self.stage not in STAGES or self.severity not in SEVERITIES or not self.href.startswith("/"):
            raise ValueError(f"not an inbox item: {self.kind} ({self.stage}, {self.severity}, {self.href})")

    @property
    def id(self) -> str:
        return f"{self.kind}-{self.source_id}"

    def fields(self) -> dict:
        """The document, less what is filled in on writing: read starts false, created_at is Firestore's clock."""
        return {"kind": self.kind, "stage": self.stage, "title": self.title, "body": self.body, "href": self.href,
                "severity": self.severity, "actor": self.actor}


@dataclass(frozen=True)
class Delivery:
    person_id: str
    item: Item


class Sink(Protocol):
    def write(self, deliveries: list[Delivery]) -> None: ...


class FirestoreSink:
    """Writes each delivery to people/{person_id}/inbox/{item id}."""

    def __init__(self) -> None:
        self._client = None
        self._lock = threading.Lock()

    def _db(self):
        with self._lock:  # made on the first write, so no cold start waits for it
            if self._client is None:
                from firebase_admin import firestore

                from app.realtime.firebase import firebase_app

                self._client = firestore.client(app=firebase_app())
            return self._client

    def write(self, deliveries: list[Delivery]) -> None:
        from firebase_admin import firestore

        db = self._db()
        for chunk in batched(deliveries, BATCH):
            batch = db.batch()
            for d in chunk:
                doc = db.collection("people").document(d.person_id).collection("inbox").document(d.item.id)
                batch.set(doc, {**d.item.fields(), "read": False, "created_at": firestore.SERVER_TIMESTAMP})
            batch.commit(timeout=WRITE_TIMEOUT)


class Courier:
    """Hands deliveries to a small thread pool, so no request waits for Firestore. A failed write is logged and
    dropped: every notice points at a page that holds the same facts."""

    def __init__(self, sink: Sink, *, background: bool = True) -> None:
        self.sink = sink
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="inbox") if background else None
        self._pending: set[Future] = set()
        self._lock = threading.Lock()

    def send(self, deliveries: list[Delivery]) -> None:
        if self._pool is None:  # written before commit() returns: tests read the sink straight after
            self._write(deliveries)
            return
        future = self._pool.submit(self._write, deliveries)
        with self._lock:
            self._pending.add(future)
        future.add_done_callback(self._settled)

    def _settled(self, future: Future) -> None:
        with self._lock:
            self._pending.discard(future)

    def _write(self, deliveries: list[Delivery]) -> None:
        try:
            self.sink.write(deliveries)
        except Exception:  # best effort: into the log, never into a request
            log.exception("inbox: %d notice(s) not delivered", len(deliveries))

    def drain(self, timeout: float = 10.0) -> None:
        """Wait for the writes in flight; a job calls this before it exits."""
        with self._lock:
            pending = list(self._pending)
        wait(pending, timeout=timeout)


_courier: Courier | None = None
_configured = False
_config_lock = threading.Lock()


def courier() -> Courier | None:
    """This process's courier: Firestore when FIRESTORE_ENABLED is true; otherwise none, and notices do nothing.
    It writes as the transaction commits unless INBOX_BACKGROUND is set: a write is a few tens of milliseconds, and on
    Cloud Run a thread left running after the response gets no CPU until the next request comes in."""
    global _courier, _configured
    if not _configured:
        with _config_lock:
            if not _configured:
                settings = get_settings()
                _courier = (Courier(FirestoreSink(), background=settings.inbox_background)
                            if settings.firestore_enabled else None)
                _configured = True
    return _courier


def set_courier(replacement: Courier | None) -> None:
    """Swap the courier: tests record deliveries instead of writing them."""
    global _courier, _configured
    with _config_lock:
        _courier, _configured = replacement, True


def drain(timeout: float = 10.0) -> None:
    if _courier is not None:
        _courier.drain(timeout)


def people(db: Session, *kinds: str, besides: Iterable[str | None] = ()) -> list[str]:
    """Everyone of these kinds (investor, advisor, ops, compliance), less `besides`."""
    skip = set(besides)
    rows = db.scalars(select(Person.id).where(Person.kind.in_(kinds)).order_by(Person.created_at, Person.id)).all()
    return [person_id for person_id in rows if person_id not in skip]


def notify(db: Session, recipients: Iterable[str], item: Item) -> None:
    """Stage the item for each recipient; it goes out when this session's outermost transaction commits."""
    if courier() is None:
        return
    staged_in = db.get_nested_transaction() or db.get_transaction()
    outbox = db.info.setdefault(_OUTBOX, [])
    outbox.extend((staged_in, Delivery(str(person_id), item)) for person_id in dict.fromkeys(recipients))


def _within(transaction: SessionTransaction | None, outer: SessionTransaction) -> bool:
    while transaction is not None:
        if transaction is outer:
            return True
        transaction = transaction.parent
    return False


@event.listens_for(Session, "after_commit")
def _deliver(session: Session) -> None:
    # Releasing a savepoint fires after_commit too; only the outermost commit makes the work final.
    if _OUTBOX not in session.info or session.in_nested_transaction():
        return
    staged = session.info.pop(_OUTBOX)
    target = courier()
    if target is None or not staged:
        return
    once = {(d.person_id, d.item.id): d for _, d in staged}  # a notice staged twice in one transaction goes once
    try:
        target.send(list(once.values()))
    except Exception:
        log.exception("inbox: hand-off failed")


@event.listens_for(Session, "after_soft_rollback")
def _forget_savepoint(session: Session, previous_transaction: SessionTransaction) -> None:
    """A savepoint that rolls back takes back what was staged inside it."""
    staged = session.info.get(_OUTBOX)
    if staged and previous_transaction.nested:
        session.info[_OUTBOX] = [(t, d) for t, d in staged if not _within(t, previous_transaction)]


@event.listens_for(Session, "after_transaction_end")
def _forget(session: Session, transaction: SessionTransaction) -> None:
    """The outermost transaction ended without delivering (a rollback, or a close without a commit)."""
    if transaction.parent is None:
        session.info.pop(_OUTBOX, None)
