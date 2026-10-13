"""The evaluation framework: suites register themselves, cases run on a scratch database, and every case is a pass,
a fail, or an error (the model could not be reached), never a guess."""
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

TIERS = ("free", "live")
KINDS = ("golden", "red_team", "fairness", "challenger")


@dataclass
class CaseResult:
    case_id: str
    outcome: str  # "pass" | "fail" | "error"
    expected: Any = None
    actual: Any = None
    detail: str = ""
    cost_usd: float = 0.0
    latency_ms: int = 0


@dataclass
class SuiteResult:
    model_key: str
    kind: str
    tier: str
    bar: str     # the pass bar in words, e.g. "AUC at least 0.75 on 400 held-out leads"
    metric: str  # what this run measured, e.g. "AUC 0.79 on 400 held-out leads"
    passed: bool
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {o: sum(c.outcome == o for c in self.cases) for o in ("pass", "fail", "error")}

    @property
    def cost_usd(self) -> float:
        return round(sum(c.cost_usd for c in self.cases), 6)


@dataclass
class EvalContext:
    tier: str
    llm: Any = None          # an LLM for live suites; None in the free tier
    agent_model: Any = None  # the ADK model for live agent suites; None in the free tier
    with_documents: bool = False


@dataclass(frozen=True)
class Suite:
    model_key: str
    kind: str
    tier: str
    needs_documents: bool
    fn: Callable[[EvalContext], SuiteResult]


SUITES: list[Suite] = []


def suite(model_key: str, *, kind: str = "golden", tier: str = "free", needs_documents: bool = False):
    """Register a suite. Suite modules live in app.governance.evals.suites and load_suites() imports them all."""
    from app.governance.inventory import MODELS

    if model_key not in MODELS:
        raise ValueError(f"No model called {model_key} in the inventory")
    if kind not in KINDS or tier not in TIERS:
        raise ValueError(f"Unknown suite kind {kind!r} or tier {tier!r}")

    def register(fn: Callable[[EvalContext], SuiteResult]):
        SUITES[:] = [s for s in SUITES if (s.fn.__module__, s.fn.__qualname__) != (fn.__module__, fn.__qualname__)]
        SUITES.append(Suite(model_key, kind, tier, needs_documents, fn))
        return fn

    return register


def load_suites() -> list[Suite]:
    import importlib
    import pkgutil

    import app.governance.evals.suites as package

    for module in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"{package.__name__}.{module.name}")
    return sorted(SUITES, key=lambda s: (s.model_key, s.kind, s.tier))


def models_with_suites() -> set[str]:
    return {s.model_key for s in load_suites()}


@contextmanager
def scratch_db() -> Iterator[Session]:
    """A fresh in-memory database with every table, so cases never touch the live one."""
    import app.models  # noqa: F401  registers every table
    from app.db import Base, make_engine

    engine = make_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def ai_cost(db: Session) -> float:
    """What the AI calls recorded in this database have cost so far."""
    from app.models import AIDecision

    return float(db.scalar(select(func.coalesce(func.sum(AIDecision.cost_usd), 0))) or 0)


def run_case(case_id: str, check: Callable[[], CaseResult], *, db: Session | None = None) -> CaseResult:
    """Time a case, charge it the AI cost it recorded, and turn an unreachable model into an error, not a fail."""
    from app.agents.runtime import AgentUnavailable
    from app.ai.llm import LLMError

    before = ai_cost(db) if db is not None else 0.0
    started = time.perf_counter()
    try:
        result = check()
    except (LLMError, AgentUnavailable) as e:
        result = CaseResult(case_id, "error", detail=f"The model could not be reached: {e}")
    result.latency_ms = int((time.perf_counter() - started) * 1000)
    if db is not None:
        result.cost_usd = round(ai_cost(db) - before, 6)
    return result


def share_passing(cases: list[CaseResult]) -> float | None:
    """The share of judged cases that passed; None when every case errored."""
    judged = [c for c in cases if c.outcome != "error"]
    return sum(c.outcome == "pass" for c in judged) / len(judged) if judged else None


def rate(model_key: str, kind: str, tier: str, cases: list[CaseResult], *, bar: str, metric: str,
         value: float | None, threshold: float) -> SuiteResult:
    """A suite judged by one measured value against its bar. With no value, there is no result, and no pass."""
    if value is None:
        return SuiteResult(model_key, kind, tier, bar, "No result: the model could not be reached", False, cases)
    return SuiteResult(model_key, kind, tier, bar, metric, value >= threshold, cases)


def every_case(model_key: str, kind: str, tier: str, cases: list[CaseResult], *, bar: str) -> SuiteResult:
    """A suite that passes only when every judged case passes. In a live suite, a case whose model could not be
    reached is not judged (one quota error must not fail, or pause, a model that answered every other case well);
    with no judged case there is no result. The free tier has no model to blame, so there an error is a failure."""
    judged = cases if tier == "free" else [c for c in cases if c.outcome != "error"]
    if cases and not judged:
        return SuiteResult(model_key, kind, tier, bar, "No result: the model could not be reached", False, cases)
    good = sum(c.outcome == "pass" for c in judged)
    unreached = len(cases) - len(judged)
    metric = f"{good} of {len(judged)} cases passed" + (f" ({unreached} could not reach the model)" if unreached else "")
    return SuiteResult(model_key, kind, tier, bar, metric, bool(judged) and good == len(judged), cases)


def within_misses(model_key: str, kind: str, tier: str, cases: list[CaseResult], *, bar: str, metric: str,
                  judged: int, misses: int, max_misses: int) -> SuiteResult:
    """A suite judged by how many judged items missed, for samples too small for a percentage: at 18 pairs, 95% means
    none may miss, which reads one run-to-run flip as a finding."""
    if judged == 0:
        return SuiteResult(model_key, kind, tier, bar, "No result: the model could not be reached", False, cases)
    return SuiteResult(model_key, kind, tier, bar, metric, misses <= max_misses, cases)
