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
    try:
        plan.redemption = preview_redemption(fund.code, open_lots(db, account.id, fund.code), price.nav, price.as_of,
                                             amount=amount, units=units)
        plan.checks.append(Check("HOLDING", True, f"You hold enough {fund.name} units."))
    except InsufficientUnits as e:
        plan.checks.append(Check("HOLDING", False, str(e)))
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
