from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import AccountDevice
from app.services.devices import aware, device_hash, device_label, first_seen, see_device

CHROME = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 "
          "Safari/537.36")
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
          "Version/18.0 Mobile/15E148 Safari/604.1")


def test_only_a_hash_of_the_browser_identifier_is_kept():
    assert device_hash("  ") is None and device_hash(None) is None
    hashed = device_hash("4f1c-browser-id")
    assert len(hashed) == 32 and "4f1c" not in hashed and hashed == device_hash("4f1c-browser-id")


def test_labels_are_rough_and_readable():
    assert device_label(CHROME) == "Chrome on Windows"
    assert device_label(IPHONE) == "Safari on iPhone"
    assert device_label(None) == "Unknown browser"


def test_seeing_a_device_keeps_its_first_sighting(db, account):
    t0 = datetime(2026, 10, 12, 9, tzinfo=timezone.utc)
    see_device(db, account.id, "h1", "Chrome on Windows", t0)
    see_device(db, account.id, "h1", "Chrome on Windows", t0 + timedelta(hours=3))
    assert first_seen(db, account.id, "h1") == t0
    assert first_seen(db, account.id, "h2") is None
    rows = db.scalars(select(AccountDevice)).all()
    assert len(rows) == 1 and aware(rows[0].last_seen) == t0 + timedelta(hours=3)
