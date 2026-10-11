"""Demo leads: seven genuine prospects and three fraud stories. All people and contact details are synthetic.

Fraud stories:
1. Synthetic identity (Alex Mercer): throwaway email, malformed phone, $250,000 with $20,000 a month on a
   one-year horizon, unexplained source of funds, machine-sounding notes.
2. Device ring (Jordan Lee, Taylor Kim, Casey Morgan): same device as Alex within half an hour, throwaway emails.
3. Duplicate contact (M. Chen): reuses Michael Chen's phone number with a different email.
"""
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Lead, Person
from app.models.base import utcnow

DEMO_LEADS: list[dict] = [
    dict(minutes=600, source="referral", full_name="Emma Walsh", email="emma.walsh@example.com", phone="+16175550188",
         goals="Retire by 55 and keep growing what I have saved so far", horizon_years=15, investable_usd="150000",
         monthly_usd="1500", source_of_funds="salary", notes="Referred by a colleague who already invests with you.",
         device_id="dev-emma-0001"),
    dict(minutes=540, source="web", full_name="Michael Chen", email="m.chen@example.com", phone="+16175550142",
         goals="Save for my two kids' college over the next ten years", horizon_years=10, investable_usd="40000",
         monthly_usd="300", source_of_funds="salary", device_id="dev-chen-0001"),
    dict(minutes=480, source="event", full_name="Sarah Okonkwo", email="sarah.okonkwo@example.com",
         phone="+12125550177", goals="Preserve an inheritance and draw a modest income from it", horizon_years=7,
         investable_usd="500000", monthly_usd="0", source_of_funds="inheritance",
         notes="Met at the Boston retirement planning seminar.", device_id="dev-okon-0001"),
    dict(minutes=420, source="web", full_name="James Patel", email="james.patel@example.com", phone="+14155550199",
         goals="Aggressive long-term growth, mostly technology", horizon_years=25, investable_usd="25000",
         monthly_usd="1000", source_of_funds="salary", device_id="dev-patel-001"),
    dict(minutes=360, source="email", full_name="Linda Morales", email="linda.morales@example.com",
         phone="+13055550123", goals="Steady income to help pay for my parents' care", horizon_years=5,
         investable_usd="80000", monthly_usd="400", source_of_funds="savings", device_id="dev-mora-0001"),
    dict(minutes=300, source="referral", full_name="Kenji Watanabe", email="kenji.w@example.com", phone="+12065550111",
         goals="Diversify globally beyond US stocks for the long run", horizon_years=20, investable_usd="220000",
         monthly_usd="2000", source_of_funds="business", device_id="dev-wata-0001"),
    dict(minutes=240, source="web", full_name="Olivia Brooks", email="olivia.brooks@example.com",
         phone="+15125550100", goals="Just starting out and want to invest a little every month", horizon_years=30,
         investable_usd="12000", monthly_usd="200", source_of_funds="salary", device_id="dev-broo-0001"),
    dict(minutes=95, source="web", full_name="Alex Mercer", email="alex.mercer@mailinator.com", phone="5551234",
         goals="Maximize growth aggressively", horizon_years=1, investable_usd="250000", monthly_usd="20000",
         source_of_funds="unspecified",
         notes="I am writing to express my keen interest in your esteemed investment services. Kindly process my "
               "application at your earliest convenience so that I may commence investing without delay.",
         device_id="dev-ring-0001"),
    dict(minutes=80, source="web", full_name="Jordan Lee", email="jordan.lee@yopmail.com", phone="+15555550101",
         goals="High growth", horizon_years=1, investable_usd="240000", monthly_usd="15000",
         source_of_funds="unspecified", device_id="dev-ring-0001"),
    dict(minutes=72, source="web", full_name="Taylor Kim", email="t.kim@guerrillamail.com", phone="+15555550102",
         goals="High growth", horizon_years=1, investable_usd="245000", monthly_usd="15000",
         source_of_funds="unspecified", device_id="dev-ring-0001"),
    dict(minutes=65, source="web", full_name="Casey Morgan", email="casey.m@sharklasers.com", phone="+15555550103",
         goals="High growth", horizon_years=1, investable_usd="238000", monthly_usd="15000",
         source_of_funds="unspecified", device_id="dev-ring-0001"),
    dict(minutes=30, source="web", full_name="M. Chen", email="mchen.invest@example.net", phone="+16175550142",
         goals="Grow money for college", horizon_years=10, investable_usd="45000", monthly_usd="300",
         source_of_funds="salary", device_id="dev-chen-0002"),
]


def seed_demo_leads(db: Session) -> int:
    """Insert the demo leads, unscored, only when the lead table is empty."""
    if db.scalar(select(func.count()).select_from(Lead)):
        return 0
    owner = db.scalar(select(Person).where(Person.email == "daniel@atrium.demo"))
    now = utcnow()
    for spec in DEMO_LEADS:
        fields = {k: v for k, v in spec.items() if k != "minutes"}
        lead = Lead(**{**fields, "investable_usd": Decimal(fields["investable_usd"]),
                       "monthly_usd": Decimal(fields["monthly_usd"]), "country": "US", "ip_hash": "seed",
                       "owner_id": owner.id if owner else None})
        lead.created_at = now - timedelta(minutes=spec["minutes"])
        db.add(lead)
    db.flush()
    return len(DEMO_LEADS)
