from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select

from app.ai.decisions import record_decision
from app.ai.llm import LLMResult
from app.events import InProcessEventBus, set_event_bus
from app.models import AIDecision


class Out(BaseModel):
    verdict: str


def test_record_decision_persists_output_and_emits_metadata_only_event(db):
    bus = InProcessEventBus()
    set_event_bus(bus)
    result = LLMResult(parsed=Out(verdict="clear"), model="gemini-3.8-flash", tokens_in=1200,
                       tokens_out=300, latency_ms=850, cost_usd=0.002025)
    row = record_decision(db, agent="trust", purpose="lead_enrichment", result=result,
                          subject_type="lead", subject_id="L1", input_text="secret prompt", confidence=0.8)
    db.commit()
    stored = db.scalar(select(AIDecision))
    assert stored.id == row.id and stored.output == {"verdict": "clear"}
    assert stored.cost_usd == Decimal("0.002025") and stored.tokens_out == 300 and stored.confidence == 0.8
    assert len(stored.input_digest) == 64 and "secret" not in stored.input_digest
    event = bus.history[-1]
    assert event.type == "AIDecisionRecorded" and event.payload["decision_id"] == row.id
    assert "output" not in event.payload and event.payload["subject_id"] == "L1"
