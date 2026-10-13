"""Seeds for the Fraud ring radar: the link that joins the lead device ring to a client account.

The device the Alex Mercer, Jordan Lee, Taylor Kim and Casey Morgan applications came from (`dev-ring-0001`) also
signed in to Sofia Rossi's account, from the day her $45,000 came in to the day $42,000 went out again. Acquire alone
sees a device ring and Operate alone sees a mule account; the radar shows one network. The four applications also
came from one network, a weak link the radar draws dashed and never uses to join anyone.
"""
import hashlib
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountDevice, Lead, Person, Posting
from app.models.base import utcnow
from app.services.devices import device_hash

RING_DEVICE = "dev-ring-0001"
RING_CLIENT = "sofia@atrium.demo"
RING_NETWORK = hashlib.sha256(b"atrium-demo:ring-network").hexdigest()[:32]
MONEY_IN_DAYS = 10  # the money-in-and-straight-out window (app/services/aml.py RAPID_DAYS)


def _at(day: date) -> datetime:
    return datetime.combine(day, time(15), tzinfo=timezone.utc)


def _money_days(db: Session, account: Account) -> tuple[datetime, datetime]:
    """The day the largest payment came in before the last redemption, and that redemption's day."""
    postings = db.scalars(select(Posting).where(Posting.account_id == account.id, Posting.instrument_type == "fund",
                                                Posting.posting_type.in_(("subscription", "redemption")))).all()
    outs = sorted((p for p in postings if p.posting_type == "redemption"), key=lambda p: p.value_date)
    if not outs:
        now = utcnow()
        return now - timedelta(days=1), now
    out_day = outs[-1].value_date
    ins = [p for p in postings if p.posting_type == "subscription"
           and 0 <= (out_day - p.value_date).days <= MONEY_IN_DAYS]
    in_day = min(ins, key=lambda p: p.cash).value_date if ins else out_day
    return _at(in_day), _at(out_day)


def seed_ring_link(db: Session) -> bool:
    """Add the ring device to Sofia Rossi's account once. Returns True when it was added."""
    account = db.scalar(select(Account).join(Person, Account.person_id == Person.id)
                        .where(Person.email == RING_CLIENT).order_by(Account.opened_on, Account.number).limit(1))
    if account is None:
        return False
    hashed = device_hash(RING_DEVICE)
    if db.scalar(select(AccountDevice.id).where(AccountDevice.account_id == account.id,
                                                AccountDevice.device_hash == hashed)) is not None:
        return False
    first, last = _money_days(db, account)
    db.add(AccountDevice(account_id=account.id, device_hash=hashed, label="Chrome on Windows", first_seen=first,
                         last_seen=last))
    for lead in db.scalars(select(Lead).where(Lead.device_id == RING_DEVICE, Lead.ip_hash == "seed")).all():
        lead.ip_hash = RING_NETWORK
    db.flush()
    return True
