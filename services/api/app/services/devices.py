"""Devices an account is used from (Lifecycle Trust Score, trading stage). The browser keeps a random identifier and
sends it with each request; Atrium stores only a hash of it, with a rough label such as "Chrome on Windows"."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AccountDevice

# Order matters: Chrome's user agent also says Safari, and an iPhone's also says Mac OS X.
BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari"))
SYSTEMS = (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("Windows", "Windows"),
           ("Mac OS X", "macOS"), ("Linux", "Linux"))


def device_hash(raw: str | None) -> str | None:
    raw = (raw or "").strip()
    return hashlib.sha256(raw.encode()).hexdigest()[:32] if raw else None


def device_label(user_agent: str | None) -> str:
    ua = user_agent or ""
    browser = next((name for token, name in BROWSERS if token in ua), None)
    system = next((name for token, name in SYSTEMS if token in ua), None)
    if browser is None:
        return "Unknown browser"
    return f"{browser} on {system}" if system else browser


def aware(moment: datetime) -> datetime:
    """SQLite drops time zones on the way back; every time Atrium stores is UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _row(db: Session, account_id: str, hashed: str) -> AccountDevice | None:
    return db.scalar(select(AccountDevice).where(AccountDevice.account_id == account_id,
                                                 AccountDevice.device_hash == hashed))


def first_seen(db: Session, account_id: str, hashed: str) -> datetime | None:
    row = _row(db, account_id, hashed)
    return aware(row.first_seen) if row else None


def see_device(db: Session, account_id: str, hashed: str, label: str, now: datetime) -> AccountDevice:
    row = _row(db, account_id, hashed)
    if row is None:
        try:
            with db.begin_nested():
                row = AccountDevice(account_id=account_id, device_hash=hashed, label=label[:80], first_seen=now,
                                    last_seen=now)
                db.add(row)
        except IntegrityError:  # two requests from a new device at once: the other one recorded it
            row = _row(db, account_id, hashed)
    row.last_seen = now
    db.flush()
    return row
