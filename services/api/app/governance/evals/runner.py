"""Run the suites with the live event stream silenced, store every result in one transaction, and trip the breakers
the results call for."""
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import InProcessEventBus, current_bus, emit, set_event_bus
from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, load_suites
from app.governance.inventory import MODELS, versions
from app.models import EvalCase, EvalRun
from app.models.base import utcnow

RUN_TIMEOUT = timedelta(minutes=20)  # the job's task timeout: a run still running after this did not finish
COOLDOWN = timedelta(hours=1)
TRIP_KINDS = ("golden", "red_team", "fairness")  # a challenger's result is evidence, never a trip


@dataclass
class RunReport:
    tier: str
    suites: list[SuiteResult]
    models: dict[str, str]
    started_at: datetime
    finished_at: datetime

    @property
    def passed(self) -> bool:
        return all(s.passed for s in self.suites)

    @property
    def cost_usd(self) -> float:
        return round(sum(s.cost_usd for s in self.suites), 6)

    def failures(self) -> list[SuiteResult]:
        return [s for s in self.suites if not s.passed]


class quiet_events:
    """Cases run real services, which emit events; none of those may reach the live event stream."""

    def __enter__(self):
        self._saved = current_bus()
        set_event_bus(InProcessEventBus())
        return self

    def __exit__(self, *exc) -> bool:
        set_event_bus(self._saved)
        return False


def run_evals(tier: str, *, llm=None, agent_model=None, with_documents: bool = False, only: set[str] | None = None,
              now: datetime | None = None) -> RunReport:
    started = now or utcnow()
    chosen = [s for s in load_suites()
              if (s.tier == "free" or tier == "live") and (with_documents or not s.needs_documents)
              and (only is None or s.model_key in only)]
    results: list[SuiteResult] = []
    with quiet_events():
        for s in chosen:
            live = s.tier == "live"
            ctx = EvalContext(tier=s.tier, llm=llm if live else None, agent_model=agent_model if live else None,
                              with_documents=with_documents)
            try:
                results.append(s.fn(ctx))
            except Exception as e:  # a broken suite is a failed suite, never a crashed run
                results.append(SuiteResult(s.model_key, s.kind, s.tier, "The suite runs",
                                           f"The suite failed to run: {e}", False,
                                           [CaseResult("suite", "error", detail=repr(e))]))
    return RunReport(tier, results, versions(), started, utcnow())


def aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def start_run(db: Session, *, tier: str, trigger: str, requested_by: str | None = None,
              now: datetime | None = None) -> EvalRun:
    run = EvalRun(tier=tier, trigger=trigger, status="running", started_at=now or utcnow(),
                  git_sha=os.environ.get("GIT_SHA", "")[:40], requested_by=requested_by, models={}, summary={},
                  cost_usd=Decimal("0"))
    db.add(run)
    db.flush()
    return run


def adopt_or_start(db: Session, *, tier: str, trigger: str, now: datetime | None = None,
                   execution: str | None = None) -> EvalRun:
    """The job takes over the run the button asked for in the last ten minutes; otherwise it starts its own. On Cloud
    Run the execution's name tells which: an execution adopts only the run that started it, so a deploy's execution
    and a button's never write into one run. Without one (a local run), the latest button run is taken."""
    now = now or utcnow()
    asked = db.scalars(select(EvalRun).where(EvalRun.status == "running", EvalRun.trigger == "button",
                                             EvalRun.started_at >= now - timedelta(minutes=10))
                       .order_by(EvalRun.started_at.desc())).all()
    if execution:
        asked = [r for r in asked if (r.summary or {}).get("execution") == execution]
    return asked[0] if asked else start_run(db, tier=tier, trigger=trigger, now=now)


def summarise(report: RunReport) -> dict:
    return {"passed": report.passed,
            "counts": {"suites": len(report.suites), "passed": sum(s.passed for s in report.suites)},
            "suites": [{"model_key": s.model_key, "kind": s.kind, "tier": s.tier, "bar": s.bar, "metric": s.metric,
                        "passed": s.passed, "counts": s.counts, "cost_usd": s.cost_usd,
                        "case_ids": [c.case_id[:80] for c in s.cases]} for s in report.suites]}


def _jsonable(value):
    return json.loads(json.dumps(value, default=str))


def apply_breakers(db: Session, report: RunReport, run: EvalRun, *, now: datetime) -> list[str]:
    from app.governance.breakers import breaker_open, trip

    tripped: list[str] = []
    for s in report.suites:
        spec = MODELS[s.model_key]
        if s.tier != "live" or s.passed or s.kind not in TRIP_KINDS or spec.tier != "high" or not spec.fallback:
            continue
        if s.counts["pass"] + s.counts["fail"] == 0:  # every case errored: nothing was learned about the model
            continue
        if s.model_key not in tripped and not breaker_open(db, s.model_key):
            trip(db, s.model_key, reason=f"It missed its bar in the live checks ({s.metric}; the bar is {s.bar}).",
                 by="Live checks", now=now, run_id=run.id)
            tripped.append(s.model_key)
    return tripped


def store_run(db: Session, report: RunReport, run: EvalRun, *, now: datetime | None = None) -> list[str]:
    """Write every case and the summary, then trip the breakers the run calls for. Returns the tripped keys."""
    from app.ai.decisions import record_decision
    from app.ai.llm import LLMResult

    finished = now or utcnow()
    for s in report.suites:
        for c in s.cases:
            db.add(EvalCase(run_id=run.id, model_key=s.model_key, suite=s.kind, tier=s.tier, case_id=c.case_id[:80],
                            outcome=c.outcome, expected=_jsonable(c.expected), actual=_jsonable(c.actual),
                            detail=c.detail, cost_usd=Decimal(str(c.cost_usd)), latency_ms=c.latency_ms))
    run.status, run.finished_at = "finished", finished
    run.models, run.cost_usd, run.summary = report.models, Decimal(str(report.cost_usd)), summarise(report)
    db.flush()
    tripped = apply_breakers(db, report, run, now=finished)
    if run.tier == "live":  # one usage row per run keeps GET /ai/usage complete and evals separable
        record_decision(db, agent="governance", purpose="eval:live_run",
                        result=LLMResult(parsed=run.summary["counts"], model="mixed", tokens_in=0, tokens_out=0,
                                         latency_ms=int((finished - aware(run.started_at)).total_seconds() * 1000),
                                         cost_usd=report.cost_usd),
                        subject_type="eval_run", subject_id=run.id, input_text=run.id)
    emit("EvalRunFinished", {"run_id": run.id, "tier": run.tier, "trigger": run.trigger, "passed": report.passed,
                             "suites": len(report.suites), "failed": [s.model_key for s in report.failures()],
                             "cost_usd": str(run.cost_usd), "tripped": tripped})
    return tripped


def finish_failed(db: Session, run: EvalRun, error: Exception, *, now: datetime | None = None) -> None:
    run.status, run.finished_at = "failed", now or utcnow()
    run.summary = {"error": str(error)[:500]}
    db.flush()


def run_state(run: EvalRun, now: datetime | None = None) -> str:
    now = now or utcnow()
    if run.status == "running" and now - aware(run.started_at) >= RUN_TIMEOUT:
        return "did_not_finish"
    return run.status


def _clock(moment: datetime) -> str:
    return f"{moment:%H:%M} UTC"


def run_blocker(db: Session, now: datetime | None = None) -> str | None:
    """Why the button cannot start a live run now, or None when it can."""
    now = now or utcnow()
    latest = db.scalars(select(EvalRun).where(EvalRun.tier == "live").order_by(EvalRun.started_at.desc())).first()
    if latest is None:
        return None
    if run_state(latest, now) == "running":
        return f"A live run started at {_clock(aware(latest.started_at))} is still going."
    if latest.status == "finished" and latest.finished_at is not None:
        since = now - aware(latest.finished_at)
        if since < COOLDOWN:
            minutes = math.ceil((COOLDOWN - since).total_seconds() / 60)
            return f"The last live run finished at {_clock(aware(latest.finished_at))}; the next can start in {minutes} minutes."
    return None
