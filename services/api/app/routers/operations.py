"""The operations workspace (blueprint D1–D6 and D10).

Operations staff run the day-end, check draft prices and ask for their publication, upload bank statements (or the demo
sample), reconcile, decide each proposal, ask for manual matches and reversals, and approve one another's requests with
a one-time code. Nothing that changes a fact happens on one person's word.
"""
from collections import defaultdict
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Literal, TypeVar

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.reconciler import reconcile
from app.agents.runtime import get_agent_model
from app.ai.llm import LLM, get_llm
from app.auth import CurrentUser, require_roles
from app.config import get_settings
from app.db import get_db
from app.markets.quotes import NEW_YORK
from app.models import (Account, Approval, BankStatement, Fund, Instruction, InstructionStep, OpsRun, Person, Posting,
                        Price, ReconMatch, StatementLine)
from app.models.base import utcnow
from app.models.instruction import STEP_STATES
from app.models.operations import LINE_STATES
from app.ops.day_end import run_day_end
from app.seed.operations import seed_waiting
from app.services.allocation import funded_ids
from app.services.approvals import OpsError, decide
from app.services.devices import aware
from app.services.fund_pricing import last_closed_session, price_checks, request_publish
from app.services.instructions import payment_reference
from app.services.pricing import pricing_guard
from app.services.reconciliation import (accept, busy_instruction_ids, open_receipts, reject, request_manual_match,
                                         unmatched_deposits)
from app.services.reversals import request_reversal, why_not_reversible
from app.services.statements import ingest_statement, sample_statement, statement_reader

router = APIRouter(prefix="/ops", tags=["operations"])
ops = require_roles("ops", "admin")
MAX_STATEMENT_BYTES = 10 * 1024 * 1024
T = TypeVar("T")


class ReasonIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class PublishIn(ReasonIn):
    as_of: date


class ManualMatchIn(ReasonIn):
    line_ids: list[str] = Field(min_length=1, max_length=5)
    instruction_ids: list[str] = Field(min_length=1, max_length=5)


class ReversalIn(ReasonIn):
    posting_id: str = Field(max_length=32)


class NoteIn(BaseModel):
    note: str = Field(default="", max_length=500)


class ApprovalDecisionIn(NoteIn):
    approve: bool
    code: str = Field(max_length=12)


class SampleIn(BaseModel):
    fmt: Literal["pdf", "csv"] = "pdf"


def guarded(action: Callable[[], T]) -> T:
    try:
        return action()
    except OpsError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


def found(row: T | None, what: str) -> T:
    if row is None:
        raise HTTPException(status_code=404, detail=f"That {what} was not found.")
    return row


def me(db: Session, user: CurrentUser) -> Person:
    return db.get(Person, user.person_id)


def name_of(db: Session, person_id: str | None) -> str | None:
    person = db.get(Person, person_id) if person_id else None
    return person.full_name if person else None


def usd(x) -> str | None:
    return None if x is None else f"{Decimal(x):.2f}"


def run_out(run: OpsRun) -> dict:
    return {"id": run.id, "as_of": run.as_of, "triggered_by": run.triggered_by, "status": run.status,
            "steps": run.steps, "brief": run.summary, "started_at": run.created_at, "finished_at": run.finished_at}


def draft_out(view) -> dict:
    return {"fund_code": view.fund_code, "name": view.name, "as_of": view.as_of, "prev_as_of": view.prev_as_of,
            "prev_nav": None if view.prev_nav is None else f"{view.prev_nav:.6f}", "nav": f"{view.nav:.6f}",
            "move_pct": view.move_pct, "status": view.status,
            "checks": [{"code": c.code, "ok": c.ok, "detail": c.detail} for c in view.checks]}


def approval_out(db: Session, a: Approval, user: CurrentUser) -> dict:
    return {"id": a.id, "action": a.action, "summary": a.summary, "reason": a.reason, "evidence": a.evidence,
            "state": a.state, "requested_by": name_of(db, a.requested_by), "mine": a.requested_by == user.person_id,
            "requested_at": a.created_at, "decided_by": name_of(db, a.decided_by), "decided_at": a.decided_at,
            "decision_note": a.decision_note, "result": a.result}


def line_out(x: StatementLine) -> dict:
    return {"id": x.id, "statement_id": x.statement_id, "line_no": x.line_no, "value_date": x.value_date,
            "amount": usd(x.amount), "description": x.description, "remitter": x.remitter, "reference": x.reference,
            "channel": x.channel, "state": x.state}


def statement_out(db: Session, s: BankStatement, with_lines: bool = False) -> dict:
    lines = db.scalars(select(StatementLine).where(StatementLine.statement_id == s.id)
                       .order_by(StatementLine.line_no)).all()
    out = {"id": s.id, "filename": s.filename, "source": s.source, "bank_name": s.bank_name,
           "account_last4": s.account_last4, "period_start": s.period_start, "period_end": s.period_end,
           "uploaded_by": name_of(db, s.uploaded_by), "uploaded_at": s.created_at, "notes": s.notes,
           "counts": {state: sum(1 for x in lines if x.state == state) for state in LINE_STATES}}
    if with_lines:
        out["lines"] = [line_out(x) for x in lines]
    return out


def subscription_out(db: Session, instruction_id: str) -> dict:
    i = db.get(Instruction, instruction_id)
    account = db.get(Account, i.account_id)
    fund = db.get(Fund, i.fund_code)
    return {"instruction_id": i.id, "reference": payment_reference(i.id), "holder": account.person.full_name,
            "account_number": account.number, "fund_name": fund.name if fund else i.fund_code,
            "amount": usd(i.amount), "state": i.state, "requested_on": aware(i.requested_at).date()}


def match_out(db: Session, m: ReconMatch) -> dict:
    lines = sorted(db.scalars(select(StatementLine).where(StatementLine.id.in_(m.line_ids))).all(),
                   key=lambda x: (x.value_date, x.line_no))
    return {"id": m.id, "tier": m.tier, "confidence": m.confidence, "evidence": m.evidence,
            "proposed_by": m.proposed_by, "state": m.state, "lines": [line_out(x) for x in lines],
            "subscriptions": [subscription_out(db, i) for i in m.instruction_ids],
            "decided_by": name_of(db, m.decided_by), "decided_at": m.decided_at, "note": m.note,
            "approval_id": m.approval_id, "created_at": m.created_at}


def _draft_day(db: Session) -> date | None:
    return db.scalar(select(func.max(Price.as_of)).where(Price.status.in_(("draft", "checked"))))


@router.get("/overview")
def overview(db: Session = Depends(get_db), user: CurrentUser = Depends(ops)):
    as_of = last_closed_session(utcnow())
    draft_day = _draft_day(db)
    runs = db.scalars(select(OpsRun).order_by(OpsRun.created_at.desc()).limit(6)).all()
    return {"as_of": as_of, "draft_as_of": draft_day,
            "drafts": [draft_out(v) for v in price_checks(db, draft_day)] if draft_day else [],
            "unpublished": pricing_guard(db, as_of), "latest_run": run_out(runs[0]) if runs else None,
            "runs": [run_out(r) for r in runs], "waiting_for_money": len(open_receipts(db)),
            "unmatched_lines": len(unmatched_deposits(db)),
            "proposals": db.scalar(select(func.count()).select_from(ReconMatch)
                                   .where(ReconMatch.state == "proposed")) or 0,
            "pending_approvals": db.scalar(select(func.count()).select_from(Approval)
                                           .where(Approval.state == "pending")) or 0}


@router.post("/day-end")
def day_end(db: Session = Depends(get_db), llm: LLM = Depends(get_llm), user: CurrentUser = Depends(ops)):
    run = run_day_end(db, now=utcnow(), triggered_by=me(db, user).full_name, llm=llm)
    db.commit()
    return run_out(run)


@router.post("/prices/publish", status_code=201)
def ask_to_publish(body: PublishIn, db: Session = Depends(get_db), user: CurrentUser = Depends(ops)):
    approval = guarded(lambda: request_publish(db, body.as_of, me(db, user), body.reason))
    db.commit()
    return approval_out(db, approval, user)


@router.get("/blotter")
def blotter(state: str | None = None, db: Session = Depends(get_db), user: CurrentUser = Depends(ops)):
    query = select(Instruction).order_by(Instruction.requested_at.desc()).limit(80)
    if state:
        query = query.where(Instruction.state == state)
    rows = db.scalars(query).all()
    ids = [i.id for i in rows]
    funded = funded_ids(db)
    rank = {s: n for n, s in enumerate(STEP_STATES)}
    steps: dict[str, list] = defaultdict(list)
    for s in sorted(db.scalars(select(InstructionStep).where(InstructionStep.instruction_id.in_(ids))).all(),
                    key=lambda s: (aware(s.created_at), rank.get(s.state, 99))):
        steps[s.instruction_id].append({"state": s.state, "note": s.note, "at": s.created_at})
    postings = {p.reference: p for p in db.scalars(select(Posting).where(
        Posting.reference.in_(ids), Posting.posting_type == "subscription")).all()}
    out = []
    for i in rows:
        account = db.get(Account, i.account_id)
        fund = db.get(Fund, i.fund_code)
        posting = postings.get(i.id)
        out.append({"id": i.id, "reference": payment_reference(i.id) if i.type == "subscribe" else None,
                    "type": i.type, "fund_code": i.fund_code, "fund_name": fund.name if fund else i.fund_code,
                    "holder": account.person.full_name, "account_number": account.number, "amount": usd(i.amount),
                    "units": None if i.units is None else f"{Decimal(i.units):.6f}", "state": i.state,
                    "requested_at": i.requested_at, "dealing_date": i.dealing_date,
                    "funded": (i.id in funded) if i.type == "subscribe" else None, "steps": steps.get(i.id, []),
                    "posting_id": posting.id if posting else None,
                    "not_reversible_because": why_not_reversible(db, posting) if posting else None})
    return out


@router.get("/statements/sample")
def download_sample(fmt: Literal["pdf", "csv"] = "pdf", db: Session = Depends(get_db), user: CurrentUser = Depends(ops)):
    data, filename, mime = sample_statement(db, utcnow().astimezone(NEW_YORK).date(), fmt)
    return Response(content=data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/statements/sample", status_code=201)
def read_sample(body: SampleIn, db: Session = Depends(get_db), llm: LLM = Depends(get_llm),
                reader=Depends(statement_reader), user: CurrentUser = Depends(ops)):
    data, filename, mime = sample_statement(db, utcnow().astimezone(NEW_YORK).date(), body.fmt)
    statement = guarded(lambda: ingest_statement(db, data=data, filename=filename, mime_type=mime,
                                                 uploaded_by=me(db, user), llm=llm, reader=reader))
    db.commit()
    return statement_out(db, statement, with_lines=True)


@router.post("/statements", status_code=201)
async def upload_statement(file: UploadFile = File(...), db: Session = Depends(get_db), llm: LLM = Depends(get_llm),
                           reader=Depends(statement_reader), user: CurrentUser = Depends(ops)):
    data = await file.read(MAX_STATEMENT_BYTES + 1)
    if len(data) > MAX_STATEMENT_BYTES:
        raise HTTPException(status_code=413, detail="Statements up to 10 MB can be uploaded.")
    statement = guarded(lambda: ingest_statement(db, data=data, filename=file.filename or "statement",
                                                 mime_type=file.content_type or "", uploaded_by=me(db, user), llm=llm,
                                                 reader=reader))
    db.commit()
    return statement_out(db, statement, with_lines=True)


@router.get("/statements/{statement_id}")
def get_statement(statement_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(ops)):
    return statement_out(db, found(db.get(BankStatement, statement_id), "statement"), with_lines=True)


@router.get("/reconciliation")
def reconciliation(db: Session = Depends(get_db), reader=Depends(statement_reader), user: CurrentUser = Depends(ops)):
    statements = db.scalars(select(BankStatement).order_by(BankStatement.created_at.desc()).limit(8)).all()
    waiting = db.scalars(select(ReconMatch).where(ReconMatch.state.in_(("proposed", "awaiting_approval")))
                         .order_by(ReconMatch.created_at)).all()
    recent = db.scalars(select(ReconMatch).where(ReconMatch.state.in_(("accepted", "rejected")))
                        .order_by(ReconMatch.decided_at.desc()).limit(10)).all()
    busy = busy_instruction_ids(db)
    return {"reads_pdf": reader is not None, "demo": get_settings().auth_mode == "dev",
            "statements": [statement_out(db, s) for s in statements],
            "unmatched": [line_out(x) for x in unmatched_deposits(db)],
            "receipts": [{"instruction_id": r.instruction_id, "reference": r.reference,
                          "account_number": r.account_number, "holder": r.holder, "amount": usd(r.amount),
                          "fund_name": r.fund_name, "requested_on": r.requested_on,
                          "in_proposal": r.instruction_id in busy} for r in open_receipts(db)],
            "proposals": [match_out(db, m) for m in waiting], "recent": [match_out(db, m) for m in recent]}


@router.post("/demo/payments", status_code=201)
def demo_payments(db: Session = Depends(get_db), user: CurrentUser = Depends(ops)):
    """Persona demo only: another set of client subscriptions waiting for money, so each visitor has a statement to
    reconcile. With real sign-in this does not exist."""
    if get_settings().auth_mode != "dev":
        raise HTTPException(status_code=404, detail="Not Found")
    made = seed_waiting(db)
    db.commit()
    return {"added": len(made)}


@router.post("/reconcile")
def find_matches(db: Session = Depends(get_db), model=Depends(get_agent_model), user: CurrentUser = Depends(ops)):
    result = guarded(lambda: reconcile(db, model, utcnow()))
    db.commit()
    return {k: result[k] for k in ("rules", "agent", "scorer", "summary", "used_agent")}


def _locked_match(db: Session, match_id: str) -> ReconMatch:
    return found(db.scalar(select(ReconMatch).where(ReconMatch.id == match_id).with_for_update()), "proposal")


@router.post("/matches/{match_id}/accept")
def accept_match(match_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(ops)):
    match = _locked_match(db, match_id)
    guarded(lambda: accept(db, match, me(db, user), utcnow()))
    db.commit()
    return match_out(db, match)


@router.post("/matches/{match_id}/reject")
def reject_match(match_id: str, body: NoteIn, db: Session = Depends(get_db), user: CurrentUser = Depends(ops)):
    match = _locked_match(db, match_id)
    guarded(lambda: reject(db, match, me(db, user), utcnow(), body.note))
    db.commit()
    return match_out(db, match)


@router.post("/matches/manual", status_code=201)
def ask_for_manual_match(body: ManualMatchIn, db: Session = Depends(get_db), user: CurrentUser = Depends(ops)):
    approval = guarded(lambda: request_manual_match(db, body.line_ids, body.instruction_ids, me(db, user),
                                                    body.reason))
    db.commit()
    return approval_out(db, approval, user)


@router.post("/reversals", status_code=201)
def ask_for_reversal(body: ReversalIn, db: Session = Depends(get_db), user: CurrentUser = Depends(ops)):
    approval = guarded(lambda: request_reversal(db, body.posting_id, me(db, user), body.reason))
    db.commit()
    return approval_out(db, approval, user)


@router.get("/approvals")
def approvals(state: Literal["pending", "decided", "all"] = "all", db: Session = Depends(get_db),
              user: CurrentUser = Depends(ops)):
    query = select(Approval).order_by(Approval.created_at.desc()).limit(60)
    if state == "pending":
        query = query.where(Approval.state == "pending")
    elif state == "decided":
        query = query.where(Approval.state != "pending")
    return [approval_out(db, a, user) for a in db.scalars(query).all()]


@router.post("/approvals/{approval_id}/decide")
def decide_approval(approval_id: str, body: ApprovalDecisionIn, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(ops)):
    approval = found(db.scalar(select(Approval).where(Approval.id == approval_id).with_for_update()), "request")
    guarded(lambda: decide(db, approval, me(db, user), approve=body.approve, code=body.code, note=body.note))
    db.commit()
    return approval_out(db, approval, user)
