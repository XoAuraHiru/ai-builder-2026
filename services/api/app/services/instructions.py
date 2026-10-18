"""Instructions (B11): subscribe, redeem and switch between house funds, plus monthly contribution plans.

Every instruction is checked before it is accepted, and the same checks are shown to the investor first (preview). A
fund above the investor's risk band is allowed only with an explicit acknowledgement, which is recorded. Accepted
instructions are dealt at the next published price by the day-end job (Plan 5); nothing touches the ledger here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import emit
from app.models import Account, Fund, Instruction, InstructionStep, Lot, Person, RecurringPlan
from app.realtime import notices
from app.services.ledger import InsufficientUnits, q_cash, q_units
from app.services.pricing import latest_price

RECURRING_MINIMUM = Decimal("50")
ABOVE_BAND = "This fund is above your risk profile. Confirm that you understand the extra risk to continue."


class InstructionRejected(Exception):
    pass


@dataclass(frozen=True)
class Check:
    code: str
    ok: bool
    message: str


@dataclass(frozen=True)
class LotView:
    acquired_on: date
    units: Decimal
    cost_per_unit: Decimal


@dataclass
class RedemptionPreview:
    fund_code: str
    units: Decimal
    value: Decimal
    cost: Decimal
    realised_gain: Decimal
    nav: Decimal
    nav_as_of: date
    lots: list[dict]


@dataclass
class InstructionPlan:
    checks: list[Check] = field(default_factory=list)
    needs_acknowledgement: bool = False
    suitability: str | None = None
    estimate: dict = field(default_factory=dict)
    redemption: RedemptionPreview | None = None

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)


def usd(amount: Decimal) -> str:
    return f"${amount:,.2f}"


def payment_reference(instruction_id: str) -> str:
    """The reference an investor quotes when paying for a subscription: short, unambiguous, easy to find in a bank
    narration. Statements often drop the hyphen, so matching ignores it."""
    return f"ATR-{instruction_id[:8].upper()}"


def preview_redemption(fund_code: str, lots: list[LotView], nav: Decimal, nav_as_of: date, *,
                       amount: Decimal | None = None, units: Decimal | None = None) -> RedemptionPreview:
    """Which lots a sale would use, first in first out, and the gain it would realise. Writes nothing."""
    need = q_units(units if units is not None else Decimal(amount) / nav)
    held = q_units(sum((lot.units for lot in lots), Decimal("0")))
    if need <= 0:
        raise InstructionRejected("Enter an amount greater than zero.")
    if need > held:
        raise InsufficientUnits(f"You hold {held} units of {fund_code}; this needs {need}.")
    remaining, cost, used = need, Decimal("0"), []
    for lot in lots:
        if remaining <= 0:
            break
        take = min(lot.units, remaining)
        cost += take * lot.cost_per_unit
        used.append({"acquired_on": lot.acquired_on.isoformat(), "units": str(q_units(take)),
                     "cost_per_unit": str(lot.cost_per_unit)})
        remaining -= take
    value, cost = q_cash(need * nav), q_cash(cost)
    return RedemptionPreview(fund_code=fund_code, units=need, value=value, cost=cost, realised_gain=q_cash(value - cost),
                             nav=nav, nav_as_of=nav_as_of, lots=used)


def open_lots(db: Session, account_id: str, fund_code: str) -> list[LotView]:
    rows = db.scalars(select(Lot).where(Lot.account_id == account_id, Lot.instrument == fund_code,
                                        Lot.units_remaining > 0).order_by(Lot.acquired_on, Lot.created_at)).all()
    return [LotView(r.acquired_on, r.units_remaining, r.cost_per_unit) for r in rows]


PENDING_STATES = ("received", "accepted", "priced")


def committed_units(db: Session, account_id: str, fund_code: str) -> Decimal:
    """Units already promised to redemptions and switches that the day-end job has not dealt yet."""
    rows = db.scalars(select(Instruction.units).where(
        Instruction.account_id == account_id, Instruction.fund_code == fund_code,
        Instruction.type.in_(("redeem", "switch")), Instruction.state.in_(PENDING_STATES))).all()
    return q_units(sum((u for u in rows if u is not None), Decimal("0")))


def free_lots(lots: list[LotView], reserved: Decimal) -> list[LotView]:
    """The lots left once committed units are taken first in, first out, as the day-end job will take them."""
    out, remaining = [], reserved
    for lot in lots:
        take = min(lot.units, remaining)
        remaining -= take
        if lot.units - take > 0:
            out.append(LotView(lot.acquired_on, lot.units - take, lot.cost_per_unit))
    return out


def _suitability(plan: InstructionPlan, target: Fund, band: int | None) -> None:
    if band is None:
        return
    if target.risk_band > band:
        plan.needs_acknowledgement = True
        plan.suitability = (f"{target.name} is risk band {target.risk_band}; your profile is band {band}. You can go "
                            "ahead, but it carries more risk than your profile suggests.")
    else:
        plan.checks.append(Check("SUITABILITY", True,
                                 f"{target.name} (band {target.risk_band}) is within your risk profile (band {band})."))


def _minimum(fund: Fund, amount: Decimal) -> Check:
    if amount >= fund.min_investment:
        return Check("MINIMUM", True, f"Meets the {fund.name} minimum of {usd(fund.min_investment)}.")
    return Check("MINIMUM", False, f"{fund.name} needs at least {usd(fund.min_investment)}.")


def plan_instruction(db: Session, account: Account, person: Person, kind: str, fund: Fund, *,
                     amount: Decimal | None = None, units: Decimal | None = None,
                     target: Fund | None = None) -> InstructionPlan:
    plan = InstructionPlan()
    band = person.risk_band
    plan.checks.append(Check("PROFILE", band is not None, "Your risk profile is on file." if band is not None
                             else "Complete your risk profile before placing an instruction."))
    price = latest_price(db, fund.code, date.today())
    if kind == "subscribe":
        plan.checks.append(_minimum(fund, amount))
        if price is not None:
            plan.estimate = {"units": str(q_units(amount / price.nav)), "nav": str(price.nav),
                             "nav_as_of": price.as_of.isoformat()}
        _suitability(plan, fund, band)
        return plan
    if price is None:
        plan.checks.append(Check("PRICE", False, f"{fund.name} has no published price yet."))
        return plan
    lots = open_lots(db, account.id, fund.code)
    reserved = committed_units(db, account.id, fund.code)
    try:
        plan.redemption = preview_redemption(fund.code, free_lots(lots, reserved), price.nav, price.as_of,
                                             amount=amount, units=units)
        plan.checks.append(Check("HOLDING", True, f"You hold enough {fund.name} units."))
    except InsufficientUnits as e:
        held = q_units(sum((lot.units for lot in lots), Decimal("0")))
        message = str(e) if reserved <= 0 else (
            f"You hold {held} units of {fund.name}, but {reserved} are already committed to an instruction awaiting "
            f"pricing, so {q_units(max(held - reserved, Decimal('0')))} are free.")
        plan.checks.append(Check("HOLDING", False, message))
    if kind == "switch" and target is not None:
        if plan.redemption is not None:
            plan.checks.append(_minimum(target, plan.redemption.value))
        _suitability(plan, target, band)
    return plan


def submit_instruction(db: Session, account: Account, person: Person, kind: str, fund: Fund, *,
                       amount: Decimal | None = None, units: Decimal | None = None, target: Fund | None = None,
                       acknowledge_risk: bool = False) -> Instruction:
    plan = plan_instruction(db, account, person, kind, fund, amount=amount, units=units, target=target)
    failed = [c for c in plan.checks if not c.ok]
    if failed:
        raise InstructionRejected(failed[0].message)
    if plan.needs_acknowledgement and not acknowledge_risk:
        raise InstructionRejected(ABOVE_BAND)
    acknowledged = plan.needs_acknowledgement and acknowledge_risk
    instruction = Instruction(
        account_id=account.id, fund_code=fund.code, type=kind, state="accepted",
        amount=q_cash(amount) if kind == "subscribe" else None,
        units=None if kind == "subscribe" else plan.redemption.units,
        to_fund_code=target.code if target else None, acknowledged_risk=acknowledged, notes=plan.suitability)
    db.add(instruction)
    db.flush()
    checked = " ".join(c.message for c in plan.checks)
    if acknowledged:
        checked += " The investor acknowledged the extra risk."
    for state, note in (("received", "Received from the account holder."), ("checked", checked),
                        ("accepted", "Accepted. It will be dealt at the next published price.")):
        db.add(InstructionStep(instruction_id=instruction.id, state=state, note=note))
    db.flush()
    emit("InstructionReceived", {"instruction_id": instruction.id, "account_id": account.id, "type": kind,
                                 "fund_code": fund.code, "to_fund_code": instruction.to_fund_code,
                                 "acknowledged_risk": acknowledged})
    within = next((c.message for c in plan.checks if c.code == "SUITABILITY"), "")
    notices.fund_order_accepted(db, instruction, (f"You acknowledged the extra risk: {plan.suitability.split('. ')[0]}."
                                                  if acknowledged else within))
    return instruction


def create_recurring(db: Session, account: Account, person: Person, fund: Fund, amount: Decimal, day_of_month: int,
                     acknowledge_risk: bool) -> RecurringPlan:
    if person.risk_band is None:
        raise InstructionRejected("Complete your risk profile before setting up a monthly plan.")
    if amount < RECURRING_MINIMUM:
        raise InstructionRejected(f"Monthly plans start at {usd(RECURRING_MINIMUM)}.")
    plan = InstructionPlan()
    _suitability(plan, fund, person.risk_band)
    if plan.needs_acknowledgement and not acknowledge_risk:
        raise InstructionRejected(ABOVE_BAND)
    row = RecurringPlan(account_id=account.id, fund_code=fund.code, amount=q_cash(amount), day_of_month=day_of_month,
                        status="active", acknowledged_risk=plan.needs_acknowledgement and acknowledge_risk)
    db.add(row)
    db.flush()
    emit("RecurringPlanCreated", {"plan_id": row.id, "account_id": account.id, "fund_code": fund.code,
                                  "day_of_month": day_of_month, "acknowledged_risk": row.acknowledged_risk})
    return row
