"""Turn a qualified lead into an investor with an account. A person decides; risky leads need a recorded reason."""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.events import emit
from app.models import Account, Lead, Person

RISK_BAND = {"low": 2, "medium": 3, "high": 4}
CONVERTIBLE = ("qualified", "proposal", "onboarding")


class ConversionError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _next_account_number(db: Session) -> str:
    numbers = db.scalars(select(Account.number)).all()
    highest = max((int(n.split("-")[1]) for n in numbers if n.startswith("ACC-") and n[4:].isdigit()), default=0)
    return f"ACC-{highest + 1:04d}"


def convert_lead(db: Session, lead: Lead, by_email: str,
                 override_reason: str | None = None) -> tuple[Person, Account]:
    if lead.stage == "client":
        raise ConversionError(409, "lead is already a client")
    if lead.stage not in CONVERTIBLE:
        raise ConversionError(409, "qualify the lead before converting it")
    if lead.trust_band in ("high_risk", "blocked") and not (override_reason or "").strip():
        raise ConversionError(409, f"trust band '{lead.trust_band}' needs a documented override reason")
    if db.scalar(select(func.count()).select_from(Person).where(func.lower(Person.email) == lead.email.lower())):
        raise ConversionError(409, "a person with this email already exists")
    appetite = (lead.enrichment or {}).get("stated_risk_appetite")
    person = Person(kind="investor", full_name=lead.full_name, email=lead.email.lower(), country=lead.country,
                    risk_band=RISK_BAND.get(appetite))
    db.add(person)
    db.flush()
    account = Account(person_id=person.id, number=_next_account_number(db), opened_on=date.today())
    db.add(account)
    db.flush()
    lead.stage, lead.converted_person_id = "client", person.id
    emit("ClientOnboarded", {"lead_id": lead.id, "person_id": person.id, "account_id": account.id,
                             "trust_score": lead.trust_score, "trust_band": lead.trust_band,
                             "override_reason": override_reason, "by": by_email})
    return person, account
