"""The Fraud ring radar (compliance only): rings found across leads and clients, each ring's graph, Gemini's reading
of it, and the two actions a person may take: open a case, or flag the leads."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.llm import LLM, LLMError, get_llm
from app.auth import CurrentUser, require_roles
from app.db import get_db
from app.governance.breakers import BreakerOpen
from app.realtime import notices
from app.routers.operations import me
from app.services.devices import aware
from app.services.rings import (STRONG, Graph, Ring, RingError, build_graph, case_for, detect_rings, flag_leads,
                                flagged_lead_ids, link_detail, narrate_ring, open_case)

router = APIRouter(prefix="/compliance", tags=["rings"])
mlro = require_roles("compliance", "admin")
CHANGED = "This ring has changed; reload it."
NOT_FOUND = "That ring was not found; reload the rings."
NARRATIVE_BUSY = "The ring narrative is unavailable right now; the ring and its links are all still here."


class RingActionIn(BaseModel):
    members: list[str] = Field(default_factory=list, max_length=500)  # the members the page showed


def ring_out(db: Session, ring: Ring, graph: Graph) -> dict:
    flagged = flagged_lead_ids(db, ring.id)
    case = case_for(db, ring.id)
    members = [graph.entities[m] for m in ring.members]
    return {"id": ring.id, "score": ring.score,
            "members": [{"id": e.id, "kind": e.kind, "label": e.label, "flags": list(e.flags), "flagged": e.flagged,
                         "ring_flagged": e.kind == "lead" and e.id.split(":", 1)[1] in flagged} for e in members],
            "stages": ring.stages, "strongest": ring.strongest, "strongest_kind": ring.strongest_kind,
            "strongest_members": ring.strongest_members, "identifiers": len(ring.identifiers),
            "strong_identifiers": sum(graph.identifiers[i].kind in STRONG for i in ring.identifiers),
            "links": len(ring.links), "created_span_hours": ring.created_span_hours,
            "case_alert_id": case.id if case else None,
            "case": {"id": case.id, "title": case.title, "state": case.state} if case else None,
            "flagged_leads": sum(e.kind == "lead" and e.id.split(":", 1)[1] in flagged for e in members)}


def ring_detail(db: Session, ring: Ring, graph: Graph) -> dict:
    entity, ident = graph.entities, graph.identifiers
    nodes = [{"id": m, "kind": entity[m].kind, "label": entity[m].label, "flagged": entity[m].flagged}
             for m in ring.members]
    nodes += [{"id": i, "kind": ident[i].kind, "label": ident[i].label, "flagged": False} for i in ring.identifiers]
    edges = [{"source": link.entity, "target": link.identifier, "label": link.id, "strong": link.strong,
              "id": link.id} for link in ring.links]
    rows = [{"id": link.id, "member": entity[link.entity].label, "member_kind": entity[link.entity].kind,
             "identifier": ident[link.identifier].label, "kind": ident[link.identifier].kind,
             "strength": "strong" if link.strong else "weak", "detail": link_detail(link, graph),
             "seen_at": aware(link.seen_at) if link.seen_at else None} for link in ring.links]
    return {**ring_out(db, ring, graph), "graph": {"nodes": nodes, "edges": edges}, "link_rows": rows}


def resolve(db: Session, ring_id: str, seen: list[str] | None = None) -> tuple[Ring, Graph]:
    """Re-read the ring by id. A ring the page saw that no longer resolves to the same members is a 409."""
    graph = build_graph(db)
    ring = next((r for r in detect_rings(graph) if r.id == ring_id), None)
    if ring is None:
        raise HTTPException(status_code=409 if seen else 404, detail=CHANGED if seen else NOT_FOUND)
    if seen and sorted(seen) != ring.members:
        raise HTTPException(status_code=409, detail=CHANGED)
    return ring, graph


def _acted(action):
    try:
        return action()
    except RingError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e


@router.get("/rings")
def list_rings(db: Session = Depends(get_db), user: CurrentUser = Depends(mlro)):
    graph = build_graph(db)
    out = [ring_out(db, r, graph) for r in detect_rings(graph)]
    return {"rings": out, "strongest": out[0] if out else None}


@router.get("/rings/{ring_id}")
def get_ring(ring_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(mlro)):
    ring, graph = resolve(db, ring_id)
    return ring_detail(db, ring, graph)


@router.post("/rings/{ring_id}/narrate")
def narrate(ring_id: str, body: RingActionIn | None = None, db: Session = Depends(get_db),
            llm: LLM = Depends(get_llm), user: CurrentUser = Depends(mlro)):
    ring, graph = resolve(db, ring_id, body.members if body else None)
    try:
        out = narrate_ring(db, llm, ring, graph)
    except BreakerOpen as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except LLMError as e:
        raise HTTPException(status_code=503, detail=NARRATIVE_BUSY) from e
    db.commit()
    return {**out, "narrative": out["narrative"].model_dump(mode="json")}


@router.post("/rings/{ring_id}/case", status_code=201)
def case(ring_id: str, body: RingActionIn | None = None, db: Session = Depends(get_db),
         user: CurrentUser = Depends(mlro)):
    ring, graph = resolve(db, ring_id, body.members if body else None)
    person = me(db, user)
    alert = _acted(lambda: open_case(db, ring, person, graph))
    notices.alerts_raised(db, [alert], actor=person.full_name, besides=person.id)
    db.commit()
    return {"alert_id": alert.id, "title": alert.title, "ring": ring_out(db, ring, graph)}


@router.post("/rings/{ring_id}/flag-leads")
def flag(ring_id: str, body: RingActionIn | None = None, db: Session = Depends(get_db),
         user: CurrentUser = Depends(mlro)):
    ring, graph = resolve(db, ring_id, body.members if body else None)
    flagged = _acted(lambda: flag_leads(db, ring, me(db, user), graph))
    db.commit()
    ring_after, graph_after = resolve(db, ring_id)  # the leads' trust changed, so their flags and the score may have
    return {"flagged": flagged, "ring": ring_out(db, ring_after, graph_after)}
