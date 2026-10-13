"""The Model Risk Office (SR 11-7): the model inventory with each model's validation status, its card with the
evidence behind that status, and its circuit breaker."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_roles
from app.config import get_settings
from app.db import get_db
from app.governance.breakers import BreakerError, breaker_message, reset, trip
from app.governance.evals.framework import models_with_suites
from app.governance.inventory import KINDS, MODELS, missing_sources, version
from app.models import EvalCase, EvalRun, ModelBreaker, Person
from app.routers.operations import me

router = APIRouter(prefix="/governance", tags=["governance"])
mro = require_roles("compliance", "admin")


class ReasonIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class ResetIn(ReasonIn):
    code: str = Field(min_length=6, max_length=12)


def run_out(run: EvalRun | None) -> dict | None:
    from app.governance.evals.runner import run_state

    if run is None:
        return None
    return {"id": run.id, "tier": run.tier, "trigger": run.trigger, "status": run_state(run),
            "started_at": run.started_at, "finished_at": run.finished_at, "requested_by": run.requested_by,
            "cost_usd": str(run.cost_usd), "git_sha": run.git_sha, "summary": run.summary}


def latest_runs_by_model(db: Session) -> dict[str, EvalRun]:
    """For each model, the most recent finished run that judged it."""
    out: dict[str, EvalRun] = {}
    runs = db.scalars(select(EvalRun).where(EvalRun.status == "finished")
                      .order_by(EvalRun.finished_at.desc()).limit(50)).all()
    for run in runs:
        for s in run.summary.get("suites", []):
            out.setdefault(s["model_key"], run)
    return out


def _suites_for(run: EvalRun | None, key: str) -> list[dict]:
    return [s for s in (run.summary.get("suites", []) if run else []) if s["model_key"] == key]


def model_status(db: Session, key: str, run_suites: list[dict], has_suites: bool) -> str:
    breaker = db.get(ModelBreaker, key)
    if breaker is not None and breaker.state == "open":
        return "breaker_open"
    if not run_suites:  # a run's verdict, when there is one, outranks whether a suite is registered today
        return "not_validated" if has_suites else "monitored_only"
    if any(not s["passed"] and s["counts"].get("pass", 0) + s["counts"].get("fail", 0) > 0 for s in run_suites):
        return "failing"
    if any(not s["passed"] for s in run_suites):
        return "no_result"
    return "validated"


def _row(db: Session, key: str, runs: dict[str, EvalRun], with_suites: set[str]) -> dict:
    spec, run = MODELS[key], runs.get(key)
    owner = db.scalar(select(Person.full_name).where(Person.email == spec.owner)) or spec.owner
    current = version(spec)
    validated = run.models.get(key) if run else None
    return {"key": key, "name": spec.name, "kind": spec.kind, "kind_label": KINDS[spec.kind], "tier": spec.tier,
            "owner": owner, "status": model_status(db, key, _suites_for(run, key), key in with_suites),
            "version": current, "validated_version": validated,
            "changed_since_validation": validated is not None and validated != current,
            "last_validated_at": run.finished_at if run else None, "last_run_id": run.id if run else None,
            "fallback": spec.fallback}


def _known(key: str) -> None:
    if key not in MODELS:
        raise HTTPException(status_code=404, detail="Atrium has no model by that name.")


def breaker_out(db: Session, key: str) -> dict:
    row = db.get(ModelBreaker, key)
    return {"state": row.state if row else "closed", "reason": row.reason if row else "",
            "changed_by": row.changed_by if row else None, "changed_at": row.changed_at if row else None,
            "history": row.history if row else [], "message": breaker_message(db, key)}


@router.get("/models")
def list_models(db: Session = Depends(get_db), user: CurrentUser = Depends(mro)):
    runs, with_suites = latest_runs_by_model(db), models_with_suites()
    rows = [_row(db, key, runs, with_suites) for key in MODELS]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    last = db.scalars(select(EvalRun).where(EvalRun.tier == "live").order_by(EvalRun.started_at.desc())).first()
    return {"models": rows, "counts": counts, "last_run": run_out(last)}


@router.get("/models/{key}")
def model_card(key: str, db: Session = Depends(get_db), user: CurrentUser = Depends(mro)):
    _known(key)
    runs, spec = latest_runs_by_model(db), MODELS[key]
    run = runs.get(key)
    cases = db.scalars(select(EvalCase).where(EvalCase.run_id == run.id, EvalCase.model_key == key)
                       .order_by(EvalCase.created_at)).all() if run else []
    def mine(c: EvalCase, s: dict) -> bool:  # one model can have two suites of a kind and tier: the ids tell them apart
        return c.suite == s["kind"] and c.tier == s["tier"] and ("case_ids" not in s or c.case_id in s["case_ids"])

    suites = [{**s, "cases": [{"case_id": c.case_id, "outcome": c.outcome, "expected": c.expected, "actual": c.actual,
                               "detail": c.detail, "cost_usd": str(c.cost_usd), "latency_ms": c.latency_ms}
                              for c in cases if mine(c, s)]}
              for s in _suites_for(run, key)]
    return {**_row(db, key, runs, models_with_suites()), "purpose": spec.purpose, "human_gate": spec.human_gate,
            "limitations": list(spec.limitations), "sources_missing": missing_sources(spec), "suites": suites,
            "breaker": breaker_out(db, key)}


@router.post("/breakers/{key}/open")
def open_breaker(key: str, body: ReasonIn, db: Session = Depends(get_db), user: CurrentUser = Depends(mro)):
    _known(key)
    try:
        trip(db, key, reason=body.reason, by=me(db, user).full_name)
    except BreakerError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    db.commit()
    return breaker_out(db, key)


@router.get("/runs")
def list_runs(limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db), user: CurrentUser = Depends(mro)):
    return [run_out(r) for r in db.scalars(select(EvalRun).order_by(EvalRun.started_at.desc()).limit(limit)).all()]


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(mro)):
    run = db.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Atrium has no evaluation run by that id.")
    return {**run_out(run), "suites": (run.summary or {}).get("suites", [])}


@router.post("/evals/run", status_code=202)
def start_live_checks(db: Session = Depends(get_db), user: CurrentUser = Depends(mro)):
    """Start the live checks through the atrium-evals job: one at a time and one an hour. With no job configured
    (local development) the free tier runs here, at once."""
    from app.governance import launcher
    from app.governance.evals.runner import finish_failed, run_blocker, run_evals, start_run, store_run
    from app.governance.monitoring import apply_monitoring_breakers

    settings = get_settings()
    person = me(db, user).full_name
    if not settings.evals_job:
        run = start_run(db, tier="free", trigger="local", requested_by=person)
        store_run(db, run_evals("free"), run)
        apply_monitoring_breakers(db)
        db.commit()
        return run_out(run)
    blocker = run_blocker(db)
    if blocker:
        raise HTTPException(status_code=409, detail=blocker)
    run = start_run(db, tier="live", trigger="button", requested_by=person)
    db.commit()
    try:
        launcher.launch_job(settings.evals_job)
    except launcher.LaunchError as e:
        finish_failed(db, run, e)
        db.commit()
        raise HTTPException(status_code=503, detail=f"The live checks could not be started: {e}") from e
    return run_out(run)


@router.get("/monitoring")
def get_monitoring(db: Session = Depends(get_db), user: CurrentUser = Depends(mro)):
    from app.governance.monitoring import monitoring

    return monitoring(db)


@router.post("/breakers/{key}/reset")
def reset_breaker(key: str, body: ResetIn, db: Session = Depends(get_db), user: CurrentUser = Depends(mro)):
    _known(key)
    try:
        reset(db, key, reason=body.reason, person=me(db, user), code=body.code)
    except BreakerError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    db.commit()
    return breaker_out(db, key)
