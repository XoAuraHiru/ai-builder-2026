"""Ledger reversals (blueprint D2): the ledger is never edited; a mistaken fund allocation is cancelled by a reversing
posting, requested by one person and approved by another with a one-time code.

Only a fund subscription whose units are all still held can be reversed: its own lot is closed and a `reversal`
posting cancels its units and cash, so every balance stays reproducible from the postings.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import emit
from app.markets.quotes import NEW_YORK
from app.models import Account, Approval, Fund, Instruction, InstructionStep, Lot, Person, Posting
from app.services.approvals import OpsError, request_approval


class ReversalError(OpsError):
    pass


def why_not_reversible(db: Session, posting: Posting) -> str | None:
    if posting.instrument_type != "fund" or posting.posting_type != "subscription" or posting.units <= 0:
        return "Only a fund allocation (a subscription posting) can be reversed here."
    instruction = db.get(Instruction, posting.reference)
    if instruction is not None and instruction.type != "subscribe":
        return ("These units came in through a switch, which is reversed as a whole, not one leg at a time; that is "
                "not supported here.")
    if db.scalar(select(Posting.id).where(Posting.reversal_of == posting.id)) is not None:
        return "This posting has already been reversed."
    lot = db.scalar(select(Lot).where(Lot.posting_id == posting.id))
    if lot is None or lot.units_remaining != lot.units_initial:
        return "Some of these units have since been redeemed, so the allocation cannot be reversed as a whole."
    return None


def request_reversal(db: Session, posting_id: str, requester: Person, reason: str) -> Approval:
    posting = db.get(Posting, posting_id)
    if posting is None:
        raise ReversalError("That posting was not found.")
    problem = why_not_reversible(db, posting)
    if problem:
        raise ReversalError(problem)
    account = db.get(Account, posting.account_id)
    fund = db.get(Fund, posting.instrument)
    summary = (f"Reverse the allocation of {posting.units} units of {fund.name} to {account.number} "
               f"(${-posting.cash:,.2f} on {posting.value_date:%B} {posting.value_date.day})")
    return request_approval(
        db, action="reverse_posting", payload={"posting_id": posting.id}, summary=summary, reason=reason,
        evidence=[{"label": "Posting", "detail": f"{posting.posting_type} of {posting.units} units at "
                                                 f"${posting.price:,.4f}, reference {posting.reference}."},
                  {"label": "Holder", "detail": f"{account.person.full_name}, account {account.number}."}],
        requested_by=requester)


def execute_reversal(db: Session, approval: Approval, approver: Person, now: datetime) -> dict:
    posting = db.get(Posting, approval.payload["posting_id"])
    problem = why_not_reversible(db, posting)
    if problem:
        raise ReversalError(problem)
    db.scalar(select(Lot).where(Lot.posting_id == posting.id)).units_remaining = Decimal("0")
    reversal = Posting(account_id=posting.account_id, instrument=posting.instrument,
                       instrument_type=posting.instrument_type, posting_type="reversal", units=-posting.units,
                       cash=-posting.cash, price=posting.price, value_date=now.astimezone(NEW_YORK).date(),
                       reference=f"REV-{posting.reference}"[:64], reversal_of=posting.id)
    db.add(reversal)
    db.flush()
    instruction = db.get(Instruction, posting.reference)
    if instruction is not None:
        instruction.state = "reversed"
        db.add(InstructionStep(instruction_id=instruction.id, state="reversed",
                               note=f"Allocation reversed by {approver.full_name}: {approval.reason}"))
    db.flush()
    emit("TransactionPosted", {"account_id": posting.account_id, "reference": reversal.reference,
                               "instrument": posting.instrument, "units": str(reversal.units),
                               "cash": str(reversal.cash), "reversal_of": posting.id})
    return {"reversal_posting_id": reversal.id, "units": str(reversal.units), "cash": str(reversal.cash)}
