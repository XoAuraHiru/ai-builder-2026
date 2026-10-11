from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_roles
from app.config import get_settings
from app.db import get_db
from app.events import emit
from app.models import Lead
from app.schemas.leads import LeadAck, LeadIn, LeadOut, StageIn
from app.services.capture_guard import check_capture_rate, ip_hash

router = APIRouter(prefix="/leads", tags=["leads"])
staff = require_roles("staff")


def lead_or_404(db: Session, lead_id: str) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"lead {lead_id} not found")
    return lead


@router.post("", response_model=LeadAck, status_code=201)
def capture_lead(body: LeadIn, request: Request, db: Session = Depends(get_db)):
    ip = ip_hash(request)
    check_capture_rate(db, body.device_id, ip, get_settings().lead_capture_limit_per_hour)
    lead = Lead(**body.model_dump(), ip_hash=ip)
    db.add(lead)
    db.flush()
    emit("LeadCreated", {"lead_id": lead.id, "source": lead.source})
    db.commit()
    return LeadAck(id=lead.id, status="received")


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
