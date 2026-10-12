"""Operations demo data, seeded once, after the trading data.

- A second operations person, Sam Ortiz, so four-eyes approvals have a maker (Mei Tanaka) and a checker; every staff
  member gets an authenticator secret, and the demo authenticator shows their current code.
- Every account gets a blind index of a synthetic bank account number. Noah Williams and Aisha Khan share one.
- Six subscriptions waiting for money today, so the sample statement exercises every reconciliation tier.
- Four AML stories, with the rows behind them:
  1. Arjun Mehta: three subscriptions just under $10,000 within a week (structuring).
  2. Sofia Rossi: $45,000 in and $42,000 out six days later (money in and straight out).
  3. Grace Li: a subscription paid by Marcus Okonkwo, matched on last week's statement (third-party funding).
  4. Noah Williams and Aisha Khan: up to $8,000 out of Noah's account (most of his cash fund) and into Aisha's four
     days later, from the same bank account (a round trip between linked accounts).
- Monitoring runs once, so the compliance workspace opens with alerts.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (Account, BankStatement, Instruction, InstructionStep, Person, ReconMatch, StatementLine)
from app.services.aml import run_monitoring
from app.services.approvals import ensure_totp_secret
from app.services.blind_index import blind_index
from app.services.instructions import payment_reference
from app.services.ledger import apply_posting, balance, q_cash, q_units
from app.services.pricing import latest_price

SAM = {"kind": "ops", "full_name": "Sam Ortiz", "email": "sam@atrium.demo", "country": "US"}
# (investor, fund, amount): waiting for money today, in the order the sample statement writes them.
WAITING = [("priya@atrium.demo", "ATR-BAL", "1500"), ("lucas@atrium.demo", "ATR-GRW", "2500"),
           ("hana@atrium.demo", "ATR-GLB", "3000"), ("tom@atrium.demo", "ATR-TEC", "5000"),
           ("sofia@atrium.demo", "ATR-DIV", "1250"), ("arjun@atrium.demo", "ATR-BAL", "800")]
STORY_EMAILS = ("arjun@atrium.demo", "sofia@atrium.demo", "grace@atrium.demo", "noah@atrium.demo",
                "aisha@atrium.demo")


def _at(day: date, hour: int = 14) -> datetime:
    return datetime.combine(day, time(hour), tzinfo=timezone.utc)


def _instruction(db: Session, account: Account, kind: str, fund: str, day: date, *, amount: Decimal | None = None,
                 units: Decimal | None = None, state: str = "settled") -> Instruction:
    row = Instruction(account_id=account.id, fund_code=fund, type=kind, amount=amount, units=units, state=state,
                      requested_at=_at(day), dealing_date=day if state == "settled" else None,
                      settled_at=_at(day, 22) if state == "settled" else None)
    db.add(row)
    db.flush()
    return row


def _subscribe(db: Session, account: Account, fund: str, amount: str, day: date) -> Instruction:
    row = _instruction(db, account, "subscribe", fund, day, amount=Decimal(amount))
    nav = latest_price(db, fund, day).nav
    apply_posting(db, account_id=account.id, instrument=fund, instrument_type="fund", posting_type="subscription",
                  units=q_units(row.amount / nav), cash=-row.amount, price=nav, value_date=day, reference=row.id)
    return row


def _accounts_by_email(db: Session) -> dict[str, Account]:
    return {email: account for account, email in db.execute(
        select(Account, Person.email).join(Person, Account.person_id == Person.id)).all()}


def seed_waiting(db: Session, now: datetime | None = None) -> list[Instruction]:
    """Subscriptions waiting for their money, one per WAITING investor, so the sample statement has payments to carry.
    The seed adds one set; in the persona demo, operations can add another from the reconciliation page."""
    now = now or datetime.now(timezone.utc)
    accounts = _accounts_by_email(db)
    made: list[Instruction] = []
    for k, (email, fund, amount) in enumerate(WAITING):
        if email not in accounts:
            continue
        row = Instruction(account_id=accounts[email].id, fund_code=fund, type="subscribe", amount=Decimal(amount),
                          state="accepted", requested_at=now - timedelta(minutes=60 - k))
        db.add(row)
        db.flush()
        db.add_all([InstructionStep(instruction_id=row.id, state="received", note="Received from the account holder."),
                    InstructionStep(instruction_id=row.id, state="accepted",
                                    note="Accepted. It will be dealt at the next published price.")])
        made.append(row)
    db.flush()
    return made


def _redeem(db: Session, account: Account, fund: str, amount: str, day: date) -> Instruction:
    nav = latest_price(db, fund, day).nav
    units = q_units(Decimal(amount) / nav)
    row = _instruction(db, account, "redeem", fund, day, units=units)
    apply_posting(db, account_id=account.id, instrument=fund, instrument_type="fund", posting_type="redemption",
                  units=-units, cash=q_cash(units * nav), price=nav, value_date=day, reference=row.id)
    return row


def seed_operations(db: Session, today: date | None = None) -> bool:
    """Seed the operations demo once. Returns False when it has already run or the investors are not there yet."""
    if db.scalar(select(Person.id).where(Person.email == SAM["email"])) is not None:
        return False
    accounts = _accounts_by_email(db)
    if not set(STORY_EMAILS) <= set(accounts):
        return False
    today = today or date.today()
    mei = db.scalar(select(Person).where(Person.email == "mei@atrium.demo"))
    db.add(Person(**SAM))
    db.flush()
    for person in db.scalars(select(Person).where(Person.kind != "investor")).all():
        ensure_totp_secret(person)

    rng = random.Random(20261012)
    for account in sorted(accounts.values(), key=lambda a: a.number):
        number = f"{rng.randint(10_000_000, 99_999_999)}{account.bank_last4 or rng.randint(1000, 9999)}"
        account.bank_index, account.bank_last4 = blind_index(number), number[-4:]
    noah, aisha = accounts["noah@atrium.demo"], accounts["aisha@atrium.demo"]
    aisha.bank_index, aisha.bank_last4 = noah.bank_index, noah.bank_last4

    stories: list[tuple[Instruction, str]] = []  # (subscription, payer on last week's statement)
    arjun = accounts["arjun@atrium.demo"]
    for days_ago, amount in ((6, "9400"), (4, "9750"), (2, "9900")):
        stories.append((_subscribe(db, arjun, "ATR-CASH", amount, today - timedelta(days=days_ago)), "ARJUN MEHTA"))
    sofia = accounts["sofia@atrium.demo"]
    stories.append((_subscribe(db, sofia, "ATR-BAL", "45000", today - timedelta(days=9)), "SOFIA ROSSI"))
    _redeem(db, sofia, "ATR-BAL", "42000", today - timedelta(days=3))
    grace = accounts["grace@atrium.demo"]
    stories.append((_subscribe(db, grace, "ATR-INC", "6000", today - timedelta(days=5)), "MARCUS OKONKWO"))
    out_day = today - timedelta(days=8)
    held = balance(db, noah.id, "ATR-CASH") * latest_price(db, "ATR-CASH", out_day).nav
    moved = min(Decimal("8000"), (held * Decimal("0.8") / 100).to_integral_value(rounding=ROUND_DOWN) * 100)
    if moved >= Decimal("1000"):
        _redeem(db, noah, "ATR-CASH", str(moved), out_day)
        stories.append((_subscribe(db, aisha, "ATR-CASH", str(moved), today - timedelta(days=4)), "AISHA KHAN"))

    content = "|".join(f"{i.id}:{i.amount}" for i, _ in stories).encode()
    statement = BankStatement(filename=f"client-money-{today - timedelta(days=1):%Y-%m-%d}.csv", mime_type="text/csv",
                              sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content), source="csv",
                              bank_name="Atrium Demo Bank, N.A.", account_last4="7781",
                              period_start=today - timedelta(days=10), period_end=today - timedelta(days=1),
                              uploaded_by=mei.id, notes=["Seeded: last week's statement, already reconciled."])
    db.add(statement)
    db.flush()
    for n, (instruction, payer) in enumerate(stories, start=1):
        reference = payment_reference(instruction.id)
        line = StatementLine(statement_id=statement.id, line_no=n, value_date=instruction.requested_at.date(),
                             amount=instruction.amount, description=f"ACH CREDIT {payer} REF {reference}",
                             remitter=payer.title(), reference=reference, channel="ACH", state="matched")
        db.add(line)
        db.flush()
        db.add(ReconMatch(line_ids=[line.id], instruction_ids=[instruction.id], tier="exact_reference",
                          confidence=0.99, evidence=[f"The reference {reference} matches.",
                                                     f"The amount ${instruction.amount:,.2f} matches."],
                          proposed_by="rules", state="accepted", decided_by=mei.id,
                          decided_at=_at(instruction.requested_at.date(), 16)))

    seed_waiting(db)
    run_monitoring(db, today)
    return True
