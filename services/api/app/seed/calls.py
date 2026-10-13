"""Seeds for Call intelligence: Ruth Alvarez, the lead of the pressure call, and the demo calls themselves.

The demo calls are scripts in app/seed/calls/*.json rendered once to MP3 by tools/make_demo_calls.py. Every person
in them is fictional.
"""
import json
from datetime import timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Lead, Person
from app.models.base import utcnow

DEMO_DIR = Path(__file__).resolve().parent / "calls"
DEMO_CALLS = ("discovery", "pressure")  # the attack call is for the red team only
RUTH_EMAIL = "ruth.alvarez@example.test"


@lru_cache
def demo_script(name: str) -> dict:
    return json.loads((DEMO_DIR / f"{name}.json").read_text(encoding="utf-8"))


def demo_audio(name: str) -> Path:
    return DEMO_DIR / f"{name}.mp3"


def seed_call_stories(db: Session) -> bool:
    """Add Ruth Alvarez as a new lead of Daniel's, once."""
    if db.scalar(select(Lead.id).where(Lead.email == RUTH_EMAIL).limit(1)):
        return False
    owner = db.scalar(select(Person).where(Person.email == "daniel@atrium.demo"))
    lead = Lead(source="referral", stage="new", full_name="Ruth Alvarez", email=RUTH_EMAIL, phone="+17865550174",
                country="US", goals="Keep my savings safe and leave something for my grandchildren", horizon_years=10,
                investable_usd=Decimal("180000"), monthly_usd=Decimal("0"), source_of_funds="inheritance",
                notes="I am 74 and recently widowed. The savings are an inheritance from my late husband. My nephew "
                      "Kevin may join our call.",
                device_id="dev-alva-0001", ip_hash="seed", owner_id=owner.id if owner else None)
    lead.created_at = utcnow() - timedelta(minutes=20)
    db.add(lead)
    db.flush()
    return True
