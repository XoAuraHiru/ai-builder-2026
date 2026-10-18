"""The compliance workspace (blueprint D7, D8 and D11): alerts with the rows behind them, the linked-entity graph,
Gemini Pro case reviews, the MLRO's decisions, and the logs of every AI decision and every four-eyes approval."""
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.ai.llm import LLM, LLMError, get_llm
from app.auth import CurrentUser, require_roles
from app.db import get_db
from app.governance.breakers import BreakerOpen, breaker_message
from app.models import Account, AIDecision, AmlAlert, Approval, Person
from app.models.base import utcnow
from app.ops.locks import serialise_operations
from app.realtime import notices
from app.routers.operations import approval_out, found, guarded, me, name_of
from app.services.aml import run_monitoring
from app.services.compliance_ai import decide_alert, linked_entities, review_alert

router = APIRouter(prefix="/compliance", tags=["compliance"])
mlro = require_roles("compliance", "admin")
REVIEW_BUSY = "The case review is unavailable right now; please try again in a minute."


class AlertDecisionIn(BaseModel):
    decision: Literal["escalate", "close"]
    note: str = Field(default="", max_length=1000)


def alert_out(db: Session, a: AmlAlert, detail: bool = False) -> dict:
    person = db.get(Person, a.person_id)
    account = db.get(Account, a.account_id) if a.account_id else None
    out = {"id": a.id, "scenario": a.scenario, "title": a.title, "severity": a.severity, "score": a.score,
           "person": {"id": person.id, "name": person.full_name, "country": person.country,
                      "risk_band": person.risk_band},
           "account_number": account.number if account else None, "summary": a.summary,
           "evidence_count": len(a.evidence), "state": a.state, "raised_at": a.created_at,
           "decided_by": name_of(db, a.decided_by), "decided_at": a.decided_at, "decision_note": a.decision_note}
    if detail:
        out |= {"evidence": a.evidence, "ai_review": a.ai_review, "graph": linked_entities(db, a),
                "review_paused": breaker_message(db, "case_reviewer")}
    return out


@router.get("/alerts")
def alerts(state: Literal["open", "escalated", "closed", "all"] = "open", db: Session = Depends(get_db),
           user: CurrentUser = Depends(mlro)):
    severity = case({"high": 0, "medium": 1, "low": 2}, value=AmlAlert.severity, else_=3)
    query = select(AmlAlert).order_by(severity, AmlAlert.created_at.desc()).limit(100)
    if state != "all":
        query = query.where(AmlAlert.state == state)
    return [alert_out(db, a) for a in db.scalars(query).all()]


@router.get("/alerts/{alert_id}")
def alert(alert_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(mlro)):
    return alert_out(db, found(db.get(AmlAlert, alert_id), "alert"), detail=True)


@router.post("/alerts/{alert_id}/review")
def review(alert_id: str, db: Session = Depends(get_db), llm: LLM = Depends(get_llm),
           user: CurrentUser = Depends(mlro)):
    row = found(db.get(AmlAlert, alert_id), "alert")
    try:
        review_alert(db, llm, row)
    except BreakerOpen as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except LLMError as e:
        raise HTTPException(status_code=503, detail=REVIEW_BUSY) from e
    db.commit()
    return alert_out(db, row, detail=True)


@router.post("/alerts/{alert_id}/decide")
def decide(alert_id: str, body: AlertDecisionIn, db: Session = Depends(get_db), user: CurrentUser = Depends(mlro)):
    row = found(db.scalar(select(AmlAlert).where(AmlAlert.id == alert_id).with_for_update()), "alert")
    guarded(lambda: decide_alert(db, row, me(db, user), body.decision, body.note, utcnow()))
    db.commit()
    return alert_out(db, row, detail=True)


@router.post("/monitoring")
def monitoring(db: Session = Depends(get_db), user: CurrentUser = Depends(mlro)):
    serialise_operations(db)  # the day-end also runs monitoring; alerts are unique by fingerprint
    raised = run_monitoring(db)
    notices.alerts_raised(db, raised, actor="Transaction monitoring", besides=user.person_id)
    db.commit()
    return {"raised": len(raised), "alerts": [alert_out(db, a) for a in raised]}


@router.get("/ai-decisions")
def ai_decisions(db: Session = Depends(get_db), user: CurrentUser = Depends(mlro)):
    rows = db.scalars(select(AIDecision).order_by(AIDecision.created_at.desc()).limit(100)).all()
    return {"count": len(rows), "cost_usd": str(sum((d.cost_usd for d in rows), Decimal("0"))),
            "tokens_in": sum(d.tokens_in for d in rows), "tokens_out": sum(d.tokens_out for d in rows),
            "decisions": [{"id": d.id, "agent": d.agent, "purpose": d.purpose, "model": d.model,
                           "subject_type": d.subject_type, "subject_id": d.subject_id, "confidence": d.confidence,
                           "tokens_in": d.tokens_in, "tokens_out": d.tokens_out, "latency_ms": d.latency_ms,
                           "cost_usd": str(d.cost_usd), "created_at": d.created_at} for d in rows]}


@router.get("/approvals")
def approvals_log(db: Session = Depends(get_db), user: CurrentUser = Depends(mlro)):
    rows = db.scalars(select(Approval).order_by(Approval.created_at.desc()).limit(100)).all()
    return [approval_out(db, a, user) for a in rows]
