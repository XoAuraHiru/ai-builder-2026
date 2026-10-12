"""Allocation (blueprint §8.3, day-end step 2).

Instructions accepted before the 4 pm New York cut-off on a trading day are dealt at that day's published price;
later ones at the next trading day's. Subscriptions receive units and settle once their payment is matched on the bank
statement; redemptions pay out and settle; switches redeem and subscribe in one go. Nothing is dealt while any house
fund lacks a published price for the dealing date (the pricing guard). Monthly plans that fall due become
subscriptions, exempt from the fund's lump-sum minimum.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import emit
from app.markets.quotes import NEW_YORK, is_trading_day
from app.models import Account, Fund, Instruction, InstructionStep, ReconMatch, RecurringPlan
from app.services.devices import aware
from app.services.ledger import InsufficientUnits, apply_posting, q_cash, q_units
from app.services.pricing import latest_price, pricing_guard

CUTOFF = time(16, 0)


def dealing_day(requested_at: datetime) -> date:
    local = aware(requested_at).astimezone(NEW_YORK)
    day = local.date()
    if is_trading_day(day) and local.time() < CUTOFF:
        return day
    day += timedelta(days=1)
    while not is_trading_day(day):
        day += timedelta(days=1)
    return day


@dataclass
class AllocationReport:
    as_of: date
    blocked: list[str] = field(default_factory=list)
    allocated: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"as_of": self.as_of.isoformat(), "blocked": self.blocked, "allocated": self.allocated,
                "rejected": self.rejected}


def funded_ids(db: Session) -> set[str]:
    """Subscriptions whose payment has been matched on a bank statement."""
    rows = db.scalars(select(ReconMatch.instruction_ids).where(ReconMatch.state == "accepted")).all()
    return {instruction_id for ids in rows for instruction_id in ids}


def _step(db: Session, instruction: Instruction, state: str, note: str) -> None:
    db.add(InstructionStep(instruction_id=instruction.id, state=state, note=note))


def settle(db: Session, instruction: Instruction, now: datetime, note: str) -> None:
    instruction.state, instruction.settled_at = "settled", now
    _step(db, instruction, "settled", note)


def _nav(db: Session, code: str, as_of: date) -> Decimal:
    return latest_price(db, code, as_of).nav  # the pricing guard has confirmed a published price on as_of


def _money(x: Decimal) -> str:
    return f"${x:,.2f}"


def _deal(db: Session, i: Instruction, as_of: date, now: datetime, names: dict[str, str], funded: set[str]) -> str:
    when = f"{as_of:%B} {as_of.day}"
    nav = _nav(db, i.fund_code, as_of)
    if i.type == "subscribe":
        units = q_units(i.amount / nav)
        apply_posting(db, account_id=i.account_id, instrument=i.fund_code, instrument_type="fund",
                      posting_type="subscription", units=units, cash=-i.amount, price=nav, value_date=as_of,
                      reference=i.id)
        i.dealing_date = as_of
        _step(db, i, "priced", f"Dealt at the {when} price of ${nav:,.4f} a unit.")
        _step(db, i, "allocated", f"{units} units of {names[i.fund_code]} allocated for {_money(i.amount)}.")
        if i.id in funded:
            settle(db, i, now, "Settled: the payment was already matched on the bank statement.")
        else:
            i.state = "allocated"
        return f"{units} units of {names[i.fund_code]} for {_money(i.amount)}"
    cash = q_cash(i.units * nav)
    apply_posting(db, account_id=i.account_id, instrument=i.fund_code, instrument_type="fund",
                  posting_type="redemption", units=-i.units, cash=cash, price=nav, value_date=as_of, reference=i.id)
    i.dealing_date = as_of
    _step(db, i, "priced", f"Dealt at the {when} price of ${nav:,.4f} a unit.")
    if i.type == "switch":
        target_nav = _nav(db, i.to_fund_code, as_of)
        units_in = q_units(cash / target_nav)
        apply_posting(db, account_id=i.account_id, instrument=i.to_fund_code, instrument_type="fund",
                      posting_type="subscription", units=units_in, cash=-cash, price=target_nav, value_date=as_of,
                      reference=i.id)
        words = (f"{i.units} units of {names[i.fund_code]} switched into {units_in} units of "
                 f"{names[i.to_fund_code]}")
        _step(db, i, "allocated", f"{words}.")
        settle(db, i, now, "Settled: the switch is complete.")
        return words
    account = db.get(Account, i.account_id)
    _step(db, i, "allocated", f"{i.units} units of {names[i.fund_code]} redeemed for {_money(cash)}.")
    settle(db, i, now, f"Settled: {_money(cash)} paid to the bank account ending {account.bank_last4 or '????'}.")
    return f"{i.units} units of {names[i.fund_code]} for {_money(cash)}"


def allocate(db: Session, as_of: date, now: datetime) -> AllocationReport:
    db.flush()  # sessions do not autoflush: matches and prices added by the caller must be visible to the reads below
    report = AllocationReport(as_of=as_of, blocked=pricing_guard(db, as_of))
    if report.blocked:
        return report
    funded = funded_ids(db)
    names = {f.code: f.name for f in db.scalars(select(Fund)).all()}
    pending = db.scalars(select(Instruction).where(Instruction.state == "accepted")
                         .order_by(Instruction.requested_at)).all()
    for i in pending:
        if dealing_day(i.requested_at) > as_of:
            continue
        try:
            words = _deal(db, i, as_of, now, names, funded)
        except InsufficientUnits as e:
            i.state = "rejected"
            _step(db, i, "rejected", f"Not dealt: the holding no longer covers it ({e}).")
            report.rejected.append({"instruction_id": i.id, "reason": f"the holding no longer covers it ({e})"})
            continue
        report.allocated.append({"instruction_id": i.id, "type": i.type, "state": i.state, "detail": words})
        emit("InstructionAllocated", {"instruction_id": i.id, "account_id": i.account_id, "type": i.type,
                                      "dealing_date": as_of.isoformat(), "state": i.state})
    db.flush()
    return report


def create_due_recurring(db: Session, as_of: date, now: datetime) -> list[Instruction]:
    """One subscription per active monthly plan whose day has come this month (never before the plan existed)."""
    made: list[Instruction] = []
    for plan in db.scalars(select(RecurringPlan).where(RecurringPlan.status == "active")).all():
        due = date(as_of.year, as_of.month, plan.day_of_month)
        if due > as_of or aware(plan.created_at).astimezone(NEW_YORK).date() > due:
            continue
        marker = f"Monthly plan {plan.id} for {as_of:%Y-%m}"
        if db.scalar(select(Instruction.id).where(Instruction.notes == marker)) is not None:
            continue
        row = Instruction(account_id=plan.account_id, fund_code=plan.fund_code, type="subscribe", state="accepted",
                          amount=plan.amount, requested_at=now, notes=marker,
                          acknowledged_risk=plan.acknowledged_risk)
        db.add(row)
        db.flush()
        _step(db, row, "received", f"Monthly plan contribution for {due:%B %Y}.")
        _step(db, row, "accepted", "Accepted. Monthly plans are exempt from the fund's lump-sum minimum.")
        emit("InstructionReceived", {"instruction_id": row.id, "account_id": row.account_id, "type": "subscribe",
                                     "fund_code": row.fund_code, "to_fund_code": None, "acknowledged_risk":
                                     row.acknowledged_risk, "recurring_plan_id": plan.id})
        made.append(row)
    db.flush()
    return made
