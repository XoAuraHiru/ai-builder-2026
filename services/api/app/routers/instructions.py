from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, assert_account_access, get_current_user
from app.db import get_db
from app.models import STEP_STATES, Account, Fund, Instruction, InstructionStep, Person, RecurringPlan
from app.routers.accounts import account_or_404
from app.schemas.instructions import (InstructionIn, InstructionOut, PlanOut, RecurringIn, RecurringOut, RedemptionOut,
                                      StepOut)
from app.services.instructions import InstructionRejected, create_recurring, plan_instruction, submit_instruction

router = APIRouter(prefix="/accounts", tags=["instructions"])
STEP_ORDER = {state: i for i, state in enumerate(STEP_STATES)}


def holder(db: Session, account_id: str, user: CurrentUser) -> tuple[Account, Person]:
    account = account_or_404(db, account_id)
    if user.person_id != account.person_id:
        raise HTTPException(status_code=403, detail="Only the account holder can place instructions."
                            if user.is_staff else "not your account")
    return account, account.person


def fund_or_404(db: Session, code: str | None) -> Fund | None:
    if code is None:
        return None
    fund = db.get(Fund, code)
    if fund is None:
        raise HTTPException(status_code=404, detail=f"fund {code} not found")
    return fund


def funds_by_code(db: Session) -> dict[str, Fund]:
    return {f.code: f for f in db.scalars(select(Fund)).all()}


def instruction_out(db: Session, i: Instruction, funds: dict[str, Fund]) -> InstructionOut:
    steps = db.scalars(select(InstructionStep).where(InstructionStep.instruction_id == i.id)).all()
    steps = sorted(steps, key=lambda s: (STEP_ORDER.get(s.state, 99), s.created_at))
    return InstructionOut(id=i.id, type=i.type, fund_code=i.fund_code, fund_name=funds[i.fund_code].name,
                          to_fund_code=i.to_fund_code,
                          to_fund_name=funds[i.to_fund_code].name if i.to_fund_code else None,
                          amount=i.amount, units=i.units, state=i.state, acknowledged_risk=i.acknowledged_risk,
                          requested_at=i.requested_at,
                          steps=[StepOut(state=s.state, note=s.note, at=s.created_at) for s in steps])


def recurring_out(plan: RecurringPlan, funds: dict[str, Fund]) -> RecurringOut:
    return RecurringOut(id=plan.id, fund_code=plan.fund_code, fund_name=funds[plan.fund_code].name, amount=plan.amount,
                        day_of_month=plan.day_of_month, status=plan.status, acknowledged_risk=plan.acknowledged_risk,
                        created_at=plan.created_at)


@router.post("/{account_id}/instructions/preview", response_model=PlanOut)
def preview(account_id: str, body: InstructionIn, db: Session = Depends(get_db),
            user: CurrentUser = Depends(get_current_user)):
    account, person = holder(db, account_id, user)
    fund, target = fund_or_404(db, body.fund_code), fund_or_404(db, body.to_fund_code)
    try:
        plan = plan_instruction(db, account, person, body.type, fund, amount=body.amount_usd, units=body.units,
                                target=target)
    except InstructionRejected as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    redemption = None
    if plan.redemption is not None:
        r = asdict(plan.redemption)
        r.pop("fund_code")
        redemption = RedemptionOut(**r)
    return PlanOut(ok=plan.ok, checks=[asdict(c) for c in plan.checks], needs_acknowledgement=plan.needs_acknowledgement,
                   suitability=plan.suitability, estimate=plan.estimate, redemption=redemption)


@router.post("/{account_id}/instructions", response_model=InstructionOut, status_code=201)
def submit(account_id: str, body: InstructionIn, db: Session = Depends(get_db),
           user: CurrentUser = Depends(get_current_user)):
    account, person = holder(db, account_id, user)
    fund, target = fund_or_404(db, body.fund_code), fund_or_404(db, body.to_fund_code)
    try:
        instruction = submit_instruction(db, account, person, body.type, fund, amount=body.amount_usd,
                                         units=body.units, target=target, acknowledge_risk=body.acknowledge_risk)
    except InstructionRejected as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    db.commit()
    return instruction_out(db, instruction, funds_by_code(db))


@router.get("/{account_id}/instructions", response_model=list[InstructionOut])
def list_instructions(account_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    account = account_or_404(db, account_id)
    assert_account_access(user, account)
    funds = funds_by_code(db)
    rows = db.scalars(select(Instruction).where(Instruction.account_id == account.id)
                      .order_by(Instruction.requested_at.desc()).limit(50)).all()
    return [instruction_out(db, i, funds) for i in rows]


@router.post("/{account_id}/recurring", response_model=RecurringOut, status_code=201)
def add_recurring(account_id: str, body: RecurringIn, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(get_current_user)):
    account, person = holder(db, account_id, user)
    fund = fund_or_404(db, body.fund_code)
    try:
        plan = create_recurring(db, account, person, fund, body.amount_usd, body.day_of_month, body.acknowledge_risk)
    except InstructionRejected as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    db.commit()
    return recurring_out(plan, funds_by_code(db))


@router.get("/{account_id}/recurring", response_model=list[RecurringOut])
def list_recurring(account_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    account = account_or_404(db, account_id)
    assert_account_access(user, account)
    funds = funds_by_code(db)
    rows = db.scalars(select(RecurringPlan).where(RecurringPlan.account_id == account.id)
                      .order_by(RecurringPlan.created_at.desc())).all()
    return [recurring_out(p, funds) for p in rows]


@router.delete("/{account_id}/recurring/{plan_id}", response_model=RecurringOut)
def cancel_recurring(account_id: str, plan_id: str, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(get_current_user)):
    account, _ = holder(db, account_id, user)
    plan = db.get(RecurringPlan, plan_id)
    if plan is None or plan.account_id != account.id:
        raise HTTPException(status_code=404, detail="monthly plan not found")
    plan.status = "cancelled"
    db.commit()
    return recurring_out(plan, funds_by_code(db))
