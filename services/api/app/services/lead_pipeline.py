"""Lead to scored lead: Gemini enrichment, then the deterministic Lead Score and Trust Score.
If Gemini is unavailable the deterministic scores still land and the lead says why the AI part is missing."""
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.llm import LLM, LLMError
from app.events import emit
from app.ml.lead_model import score_lead
from app.models import Lead
from app.models.base import utcnow
from app.services.enrichment import enrich_lead
from app.services.trust import apply_trust

log = logging.getLogger(__name__)


def process_lead(db: Session, lead: Lead, llm: LLM) -> Lead:
    try:
        enrichment = enrich_lead(db, lead, llm)
        lead.enrichment = enrichment.model_dump(mode="json")
        lead.next_best_action = enrichment.next_best_action
        lead.scoring_error = None
    except LLMError as e:
        log.warning("enrichment failed for lead %s: %s", lead.id, e)
        lead.scoring_error = f"AI enrichment unavailable: {e}"[:500]
    lead.lead_score, lead.lead_score_factors = score_lead(lead, lead.enrichment)
    report = apply_trust(db, lead)
    lead.scored_at = utcnow()
    emit("LeadScored", {"lead_id": lead.id, "lead_score": lead.lead_score, "trust_score": report.score,
                        "trust_band": report.band})
    db.flush()
    return lead


def score_pending(db: Session, llm: LLM, limit: int = 10) -> int:
    """Score a small batch so one request stays well inside Cloud Run's timeout even with rate-limit retries."""
    pending = db.scalars(select(Lead).where(Lead.scored_at.is_(None)).order_by(Lead.created_at).limit(limit)).all()
    for lead in pending:
        process_lead(db, lead, llm)
        db.commit()
    return len(pending)


def count_pending(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Lead).where(Lead.scored_at.is_(None))) or 0
