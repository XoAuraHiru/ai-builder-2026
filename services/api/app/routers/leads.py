import logging
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.advisor import get_agent_model
from app.ai.llm import LLM, LLMError, get_llm
from app.auth import CurrentUser, require_roles
from app.config import get_settings
from app.db import get_db
from app.events import emit
from app.models import AIDecision, Lead
from app.schemas.leads import AskIn, ConvertIn, IdentityCheckOut, LeadAck, LeadIn, LeadOut, StageIn
from app.services.capture_guard import check_capture_rate, ip_hash
from app.services.conversion import ConversionError, convert_lead
from app.services.lead_pipeline import process_lead, score_pending
from app.services.identity import (MAX_BYTES, DocumentTooLarge, ProofingClient, UnsupportedDocument,
                                   analyze_identity, get_proofing)
from app.services.trust import apply_trust

log = logging.getLogger(__name__)

router = APIRouter(prefix="/leads", tags=["leads"])
staff = require_roles("staff")
BUSY = "The AI assistant is busy right now; please try again in a minute."


def lead_or_404(db: Session, lead_id: str) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"lead {lead_id} not found")
    return lead


@router.post("", response_model=LeadAck, status_code=201)
def capture_lead(body: LeadIn, request: Request, db: Session = Depends(get_db), llm: LLM = Depends(get_llm)):
    ip = ip_hash(request)
    settings = get_settings()
    check_capture_rate(db, body.device_id, ip, settings.lead_capture_limit_per_hour,
                       settings.lead_capture_global_per_hour)
    lead = Lead(**body.model_dump(), ip_hash=ip)
    db.add(lead)
    db.flush()
    emit("LeadCreated", {"lead_id": lead.id, "source": lead.source})
    db.commit()
    try:
        process_lead(db, lead, llm)
        db.commit()
    except Exception:  # the prospect's submission must never fail because scoring did
        db.rollback()
        log.exception("scoring failed for lead %s; it stays pending", lead.id)
    return LeadAck(id=lead.id, status="received")


@router.post("/score-pending")
def score_pending_leads(db: Session = Depends(get_db), llm: LLM = Depends(get_llm), user: CurrentUser = Depends(staff)):
    return {"scored": score_pending(db, llm)}


@router.get("", response_model=list[LeadOut])
def list_leads(stage: str | None = Query(None), db: Session = Depends(get_db), user: CurrentUser = Depends(staff)):
    q = select(Lead).order_by(Lead.created_at.desc())
    if stage:
        q = q.where(Lead.stage == stage)
    return db.scalars(q).all()


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(staff)):
    return lead_or_404(db, lead_id)


@router.patch("/{lead_id}/stage", response_model=LeadOut)
def change_stage(lead_id: str, body: StageIn, db: Session = Depends(get_db), user: CurrentUser = Depends(staff)):
    lead = lead_or_404(db, lead_id)
    previous, lead.stage = lead.stage, body.stage
    emit("LeadStageChanged", {"lead_id": lead.id, "from": previous, "to": body.stage, "by": user.email})
    db.commit()
    return lead


@router.post("/{lead_id}/documents", response_model=IdentityCheckOut, status_code=201)
def upload_identity_document(lead_id: str, file: UploadFile = File(...), db: Session = Depends(get_db),
                             llm: LLM = Depends(get_llm), proofing: ProofingClient | None = Depends(get_proofing),
                             user: CurrentUser = Depends(staff)):
    lead = lead_or_404(db, lead_id)
    data = file.file.read(MAX_BYTES + 1)
    try:
        check = analyze_identity(db, lead, data, file.content_type or "", llm, proofing, date.today())
    except UnsupportedDocument as e:
        raise HTTPException(status_code=415, detail=str(e)) from e
    except DocumentTooLarge as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    except LLMError as e:
        log.warning("identity analysis failed for lead %s: %s", lead_id, e)
        raise HTTPException(status_code=502, detail="Document analysis is temporarily unavailable.") from e
    report = apply_trust(db, lead)
    db.commit()
    return IdentityCheckOut(id=check.id, extracted=check.extracted, fraud_signals=check.fraud_signals,
                            findings=check.findings, source=check.source, trust_score=report.score,
                            trust_band=report.band)


@router.post("/{lead_id}/rescore", response_model=LeadOut)
def rescore(lead_id: str, db: Session = Depends(get_db), llm: LLM = Depends(get_llm),
            user: CurrentUser = Depends(staff)):
    lead = process_lead(db, lead_or_404(db, lead_id), llm)
    db.commit()
    return lead


@router.get("/{lead_id}/decisions")
def lead_decisions(lead_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(staff)):
    lead_or_404(db, lead_id)
    rows = db.scalars(select(AIDecision).where(AIDecision.subject_id == lead_id)
                      .order_by(AIDecision.created_at)).all()
    return [{"id": d.id, "created_at": d.created_at, "agent": d.agent, "purpose": d.purpose, "model": d.model,
             "confidence": d.confidence, "cost_usd": str(d.cost_usd), "output": d.output} for d in rows]


@router.post("/{lead_id}/draft-reply")
def draft(lead_id: str, db: Session = Depends(get_db), llm: LLM = Depends(get_llm),
          model=Depends(get_agent_model), user: CurrentUser = Depends(staff)):
    from app.agents.advisor import AgentUnavailable, draft_reply

    try:
        out = draft_reply(db, lead_or_404(db, lead_id), llm, model)
    except AgentUnavailable as e:
        raise HTTPException(status_code=503, detail=BUSY) from e
    db.commit()
    return out


@router.post("/{lead_id}/ask")
def ask(lead_id: str, body: AskIn, db: Session = Depends(get_db), llm: LLM = Depends(get_llm),
        model=Depends(get_agent_model), user: CurrentUser = Depends(staff)):
    from app.agents.advisor import AgentUnavailable, ask_about_lead

    try:
        answer = ask_about_lead(db, lead_or_404(db, lead_id), body.question, llm, model)
    except AgentUnavailable as e:
        raise HTTPException(status_code=503, detail=BUSY) from e
    db.commit()
    return {"answer": answer}


@router.post("/{lead_id}/convert", status_code=201)
def convert(lead_id: str, body: ConvertIn, db: Session = Depends(get_db), user: CurrentUser = Depends(staff)):
    try:
        person, account = convert_lead(db, lead_or_404(db, lead_id), user.email, body.override_reason)
    except ConversionError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    db.commit()
    return {"person_id": person.id, "account_id": account.id, "account_number": account.number}
