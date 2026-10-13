"""Call intelligence: analyse a lead's recorded call (uploaded, or one of the demo calls), list its readings, apply the
updates an advisor ticks, and play the demo audio. Staff only, as the lead routes are. The audio is never stored."""
import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.llm import LLM, LLMError, get_llm
from app.auth import CurrentUser, require_roles
from app.db import get_db
from app.governance.breakers import BreakerOpen
from app.models import Lead, LeadCall, Person
from app.routers.leads import lead_or_404
from app.schemas.leads import LeadOut
from app.seed.calls import DEMO_CALLS, demo_audio, demo_script
from app.services.calls import MAX_BYTES, TOO_LARGE, CallError, UpdateField, analyze_call, apply_updates

log = logging.getLogger(__name__)

router = APIRouter(tags=["calls"])
staff = require_roles("staff")
UNAVAILABLE = "Call analysis is unavailable right now."


class CallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    source: str
    duration_s: float
    reading: dict
    dropped: dict
    applied: list
    created_at: datetime
    created_by: str


class DemoIn(BaseModel):
    name: Literal["discovery", "pressure"]


class ApplyIn(BaseModel):
    fields: list[UpdateField] = Field(min_length=1, max_length=5)


def _person(db: Session, user: CurrentUser) -> Person:
    person = db.get(Person, user.person_id) if user.person_id else None
    if person is None:
        raise HTTPException(status_code=403, detail="Only a registered person can analyse calls.")
    return person


def _analyse(db: Session, llm: LLM, lead_id: str, user: CurrentUser, *, data: bytes, mime_type: str,
             filename: str, source: str) -> LeadCall:
    lead = lead_or_404(db, lead_id)
    try:
        call = analyze_call(db, llm, lead, data=data, mime_type=mime_type, filename=filename, by=_person(db, user),
                            source=source)
    except BreakerOpen as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except CallError as e:
        db.commit()  # keeps the decision of a model call that found no speech
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    except LLMError as e:
        db.rollback()
        log.warning("call analysis failed for lead %s: %s", lead_id, e)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from e
    db.commit()
    return call


@router.get("/leads/{lead_id}/calls", response_model=list[CallOut])
def list_calls(lead_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(staff)):
    lead_or_404(db, lead_id)
    return db.scalars(select(LeadCall).where(LeadCall.lead_id == lead_id)
                      .order_by(LeadCall.created_at.desc())).all()


@router.post("/leads/{lead_id}/calls", response_model=CallOut, status_code=201)
def upload_call(lead_id: str, file: UploadFile = File(...), db: Session = Depends(get_db),
                llm: LLM = Depends(get_llm), user: CurrentUser = Depends(staff)):
    lead_or_404(db, lead_id)
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=TOO_LARGE)
    return _analyse(db, llm, lead_id, user, data=data, mime_type=file.content_type or "",
                    filename=file.filename or "recording", source="upload")


@router.post("/leads/{lead_id}/calls/demo", response_model=CallOut, status_code=201)
def analyse_demo_call(lead_id: str, body: DemoIn, db: Session = Depends(get_db), llm: LLM = Depends(get_llm),
                      user: CurrentUser = Depends(staff)):
    # A demo call belongs to the lead it was recorded with: read on any other lead it would put another person's
    # words, flags and trust signal on that lead's record.
    owner_email = demo_script(body.name)["lead_email"]
    if lead_or_404(db, lead_id).email.lower() != owner_email:
        owner = db.scalar(select(Lead.full_name).where(func.lower(Lead.email) == owner_email)) or "another lead"
        raise HTTPException(status_code=422, detail=f"The {body.name} demo call was recorded with {owner}; "
                                                    "open that lead to analyse it.")
    return _analyse(db, llm, lead_id, user, data=demo_audio(body.name).read_bytes(), mime_type="audio/mpeg",
                    filename=f"{body.name}.mp3", source="demo")


@router.post("/leads/{lead_id}/calls/{call_id}/apply")
def apply_call_updates(lead_id: str, call_id: str, body: ApplyIn, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(staff)):
    lead = lead_or_404(db, lead_id)
    call = db.get(LeadCall, call_id)
    if call is None or call.lead_id != lead.id:
        raise HTTPException(status_code=404, detail=f"call {call_id} not found for this lead")
    try:
        applied = apply_updates(db, lead, call, list(body.fields), by=_person(db, user))
    except CallError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    db.commit()
    return {"lead": LeadOut.model_validate(lead), "call": CallOut.model_validate(call), "applied": applied}


@router.get("/demo/calls/{name}.mp3")
def demo_call_audio(name: str, user: CurrentUser = Depends(staff)):
    if name not in DEMO_CALLS:
        raise HTTPException(status_code=404, detail="No demo call by that name.")
    return FileResponse(demo_audio(name), media_type="audio/mpeg")
