import hashlib
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.llm import LLMResult
from app.events import emit
from app.models import AIDecision


def record_decision(db: Session, *, agent: str, purpose: str, result: LLMResult, subject_type: str,
                    subject_id: str, input_text: str, confidence: float | None = None) -> AIDecision:
    """Persist the output in Cloud SQL; publish metadata only (no personal data) to the event stream."""
    output = result.parsed.model_dump(mode="json") if isinstance(result.parsed, BaseModel) else result.parsed
    row = AIDecision(agent=agent, purpose=purpose, model=result.model, subject_type=subject_type,
                     subject_id=subject_id, input_digest=hashlib.sha256(input_text.encode()).hexdigest(),
                     output=output, confidence=confidence, tokens_in=result.tokens_in,
                     tokens_out=result.tokens_out, latency_ms=result.latency_ms,
                     cost_usd=Decimal(str(result.cost_usd)))
    db.add(row)
    db.flush()
    emit("AIDecisionRecorded", {
        "decision_id": row.id, "agent": agent, "purpose": purpose, "model": result.model,
        "subject_type": subject_type, "subject_id": subject_id, "confidence": confidence,
        "tokens_in": result.tokens_in, "tokens_out": result.tokens_out, "latency_ms": result.latency_ms,
        "cost_usd": str(row.cost_usd)})
    return row
