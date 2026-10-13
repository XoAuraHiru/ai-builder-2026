# Atrium Advanced Implementation Plan (master: foundation, interfaces, integration)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Model Risk Office, Scenario Studio, Call intelligence and Fraud ring radar of the spec, in parallel, on one shared governance foundation.

**Architecture:** This master plan builds the shared foundation first (governance tables, the model inventory, circuit breakers, the evaluation framework and runner, router and seed stubs). Four feature plans then run in parallel, each in its own git worktree and branch cut from the foundation commit, touching disjoint files. A final integration phase merges them, wires navigation and journeys, and deploys.

**Tech Stack:** FastAPI, SQLAlchemy 2 (sessions with autoflush off), pytest, uv; Next.js 15 app router, Tailwind v4, Vitest, pnpm; Gemini on Vertex AI through google-genai, ADK 2.11; Cloud Run service and jobs.

**Spec:** `docs/superpowers/specs/2026-10-13-atrium-advanced-design.md`

**Feature plans (run in parallel after Phase F):**
- `docs/superpowers/plans/2026-10-13-advanced-model-risk.md` (branch `feat/adv-models`)
- `docs/superpowers/plans/2026-10-13-advanced-scenarios.md` (branch `feat/adv-scenarios`)
- `docs/superpowers/plans/2026-10-13-advanced-calls.md` (branch `feat/adv-calls`)
- `docs/superpowers/plans/2026-10-13-advanced-rings.md` (branch `feat/adv-rings`)

## Global Constraints

- AI proposes, people decide. No AI output changes a fact without a person's action; high-risk resets need a one-time code.
- Every AI output is written to the AI decision log (`record_decision`) with model, cost and latency.
- Every $ or % figure in AI prose is checked against the engines' figures (`unsupported_figures`); unsupported figures are shown, never hidden.
- Text inside prompts from users, documents, statements, calls and payers is data, not instructions; prompts say so.
- Synthetic data only. US and global markets only.
- `infra/preflight.sh` must pass: no tracked file contains a word from `infra/.forbidden-words`. Never write that word anywhere, including commit messages.
- Never use Application Default Credentials. Gemini, Document AI and TTS calls run on Cloud Run, or from this machine only with a gcloud CLI access token over REST (`gcloud auth print-access-token`).
- Report cost on every deploy. The statement sample stays CSV by default (`SAMPLE_STATEMENT_FORMAT`).
- Persona copy uses they/them or no pronouns.
- Models: `gemini-3.8-flash` (Flash), `gemini-3.1-pro-preview` (Pro), TTS `gemini-3.1-flash-tts-preview` with `gemini-2.5-flash-tts` as fallback; ADK 2.11.
- Design system: Atrium Daylight; the daylight colour marks AI only; pill buttons; key moments open each page.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Write source files with the Write/Edit tools or Python, never shell heredocs (they turn `\b` into a backspace). After writing, scan for control characters: `grep -rlP "[\x00-\x08\x0b\x0c\x0e-\x1f]" services/api/app apps/web/src` must list only binary files.
- Session autoflush is off: a service that reads rows it just added must `db.flush()` first.
- Shell: Windows Git Bash. Export `MSYS2_ARG_CONV_EXCL='*'` before passing URL paths like `/investor` as arguments.

## Review Focus

1. A breaker check when the breaker table is unreadable or the row is missing: the feature takes its fallback (open) when unreadable, and runs normally when the row is missing. Pinned in Task F2.
2. A live run whose cases all error (Gemini quota, network): no breaker trips, and the page says "No result" rather than "Failing". Pinned in Task F3.
3. The button pressed twice, or pressed while the deploy-triggered run is still going: the second request is refused with the running run's start time. Pinned in Task F3 (`run_blocker`) and the Model Risk plan's API task.
4. Eval cases emitting events (matches accepted, decisions recorded): nothing reaches the live event stream or the live database. Pinned in Task F3 (`quiet_events`, `scratch_db`).
5. A model whose prompt changed since its last validation: shown as "Changed since validation", never silently "Validated". Pinned in Task F4.

## File Structure

Foundation (this plan, Phase F):
- `services/api/app/models/governance.py`: `EvalRun`, `EvalCase`, `ModelBreaker`.
- `services/api/app/governance/__init__.py`, `inventory.py` (the 18 `ModelSpec`s, `version`, `versions`, `missing_sources`).
- `services/api/app/governance/breakers.py`: `breaker_open`, `breaker_message`, `ensure_closed`, `trip`, `reset`, `BreakerOpen`, `BreakerError`.
- `services/api/app/governance/evals/__init__.py`, `framework.py` (`suite`, `load_suites`, `scratch_db`, `run_case`, `rate`, `every_case`, `share_passing`), `runner.py` (`run_evals`, `start_run`, `adopt_or_start`, `store_run`, `finish_failed`, `run_blocker`, `run_state`), `__main__.py` (CLI), `suites/__init__.py`, `suites/lead_score.py`.
- `services/api/app/routers/governance.py`: models list and card, breaker open and reset.
- Stubs filled by the feature plans: `services/api/app/routers/scenarios.py`, `calls.py`, `rings.py`; `services/api/app/seed/calls.py`, `rings.py`.
- Tests: `services/api/tests/test_governance.py`, `test_governance_api.py`, `test_governance_gate.py`.

Each feature plan lists its own files. Files only the integration phase may edit: `apps/web/src/lib/nav.ts`, `nav.test.ts`, `journeys.ts`, `journeys.test.ts`, `apps/web/src/app/page.tsx`, `README.md`, `docs/superpowers/plans/README.md`.

## Shared interfaces (produced by Phase F; every feature plan consumes them)

```python
# app.governance.inventory
MODELS: dict[str, ModelSpec]        # keys listed in spec §3.2
version(spec: ModelSpec) -> str     # 10 hex chars
versions() -> dict[str, str]
missing_sources(spec: ModelSpec) -> list[str]

# app.governance.breakers
breaker_open(db: Session, key: str) -> bool             # unreadable table -> True; no row -> False
breaker_message(db: Session, key: str) -> str | None    # "Case review is paused: <reason> Since Oct 14."
ensure_closed(db: Session, key: str) -> None            # raises BreakerOpen(key, message)
trip(db, key, *, reason: str, by: str, now=None, run_id=None) -> ModelBreaker
reset(db, key, *, reason: str, person: Person, code: str, now=None) -> ModelBreaker   # BreakerError on a wrong code
class BreakerOpen(RuntimeError): key: str               # str(e) is the message the page shows
class BreakerError(ValueError)

# app.governance.evals.framework
@suite(model_key, *, kind="golden"|"red_team"|"fairness"|"challenger", tier="free"|"live", needs_documents=False)
def my_suite(ctx: EvalContext) -> SuiteResult
EvalContext(tier, llm, agent_model, with_documents)
CaseResult(case_id, outcome "pass"|"fail"|"error", expected=None, actual=None, detail="", cost_usd=0.0, latency_ms=0)
SuiteResult(model_key, kind, tier, bar, metric, passed, cases)
scratch_db() -> contextmanager[Session]        # fresh in-memory SQLite with every table
run_case(case_id, check: () -> CaseResult, *, db=None) -> CaseResult   # LLMError/AgentUnavailable -> "error"; charges AI cost
rate(model_key, kind, tier, cases, *, bar, metric, value: float | None, threshold) -> SuiteResult
every_case(model_key, kind, tier, cases, *, bar) -> SuiteResult
share_passing(cases) -> float | None           # share of non-error cases that passed
```

A feature adds its suites as new modules under `app/governance/evals/suites/` (one module per model key); they are discovered automatically, so no shared registry file is edited. A feature's service calls `ensure_closed(db, "<its key>")` (or `breaker_open`) before its model call and takes its fallback.

Stub contents the feature plans replace:

```python
# app/routers/scenarios.py, calls.py, rings.py (each)
from fastapi import APIRouter
router = APIRouter(tags=["<feature>"])
# app/seed/calls.py
def seed_call_stories(db) -> bool: return False
# app/seed/rings.py
def seed_ring_link(db) -> bool: return False
```

## Phases and execution

| Phase | Who | Where | Contents |
|---|---|---|---|
| F | Controller, inline | `feat/advanced` | Tasks F1–F4 below |
| 1–4 | Four implementer subagents in parallel, each in a git worktree | `feat/adv-models`, `feat/adv-scenarios`, `feat/adv-calls`, `feat/adv-rings`, each from the Phase F head | The four feature plans |
| I | Controller, inline | `feat/advanced` | Merge the four branches; Tasks I1–I3 below; final review; fix pass; deploy |

Merge order: models, scenarios, calls, rings. Expected trivial conflicts: `app/models/__init__.py` (calls adds `LeadCall`), `app/services/trust.py` (calls adds T08, rings adds T09), `apps/web/src/lib/compliance.ts` (rings adds the `ring` scenario copy). Resolve by keeping both sides.

---

## Phase F: foundation

### Task F1: Governance tables and the model inventory

**Files:**
- Create: `services/api/app/models/governance.py`
- Modify: `services/api/app/models/__init__.py`
- Create: `services/api/app/governance/__init__.py`, `services/api/app/governance/inventory.py`
- Test: `services/api/tests/test_governance.py`

**Interfaces:**
- Produces: `EvalRun`, `EvalCase`, `ModelBreaker`; `MODELS`, `ModelSpec`, `version`, `versions`, `missing_sources`, `KINDS`, `TIERS`, `model_id`.

- [ ] **Step 1: Write the failing tests**

```python
# file: services/api/tests/test_governance.py
"""The Model Risk Office foundation: the inventory, the breakers, the evaluation framework and its runner."""
from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from sqlalchemy import select

from app.governance import inventory
from app.governance.inventory import KINDS, MODELS, TIERS, missing_sources, version, versions

PERSONA_EMAILS = {f"{p}@atrium.demo" for p in ("daniel", "priya", "lucas", "tom", "hana", "mei", "sam", "omar")}
NOT_YET_BUILT = {"scenario_mapper", "call_analyst", "ring_narrator"}  # their modules arrive with the feature plans


def test_the_inventory_lists_every_model_once_with_what_governs_it():
    assert len(MODELS) == 18
    for key, spec in MODELS.items():
        assert spec.key == key and spec.kind in KINDS and spec.tier in TIERS, key
        assert spec.owner in PERSONA_EMAILS and spec.purpose and spec.human_gate and spec.limitations, key
        assert spec.sources, key
    high_with_fallback = {k for k, s in MODELS.items() if s.tier == "high" and s.fallback}
    assert {"reconciler_agent", "case_reviewer", "call_analyst", "draft_compliance"} <= high_with_fallback


def test_every_built_model_resolves_its_sources():
    for key, spec in MODELS.items():
        if key not in NOT_YET_BUILT:
            assert missing_sources(spec) == [], key


def test_a_version_is_stable_and_changes_when_its_text_changes(monkeypatch):
    spec = MODELS["case_reviewer"]
    first = version(spec)
    assert len(first) == 10 and version(spec) == first and versions()["case_reviewer"] == first
    real = inventory._source_text
    monkeypatch.setattr(inventory, "_source_text", lambda s: real(s) + " changed")
    assert version(spec) != first
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd services/api && uv run pytest -q -p no:warnings tests/test_governance.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.governance'`.

- [ ] **Step 3: Write the tables and the inventory**

```python
# file: services/api/app/models/governance.py
"""Model governance (the Model Risk Office): evaluation runs, their cases, and each model's circuit breaker."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin, utcnow

EVAL_TIERS = ("free", "live")
EVAL_TRIGGERS = ("deploy", "button", "local")
RUN_STATES = ("running", "finished", "failed")
CASE_OUTCOMES = ("pass", "fail", "error")
SUITE_KINDS = ("golden", "red_team", "fairness", "challenger")
BREAKER_STATES = ("closed", "open")


class EvalRun(IdMixin, Base):
    __tablename__ = "eval_run"

    tier: Mapped[str] = mapped_column(String(8), nullable=False)
    trigger: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    git_sha: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    requested_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    models: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # model key -> version
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("0"))
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class EvalCase(IdMixin, Base):
    __tablename__ = "eval_case"

    run_id: Mapped[str] = mapped_column(ForeignKey("eval_run.id"), nullable=False, index=True)
    model_key: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    suite: Mapped[str] = mapped_column(String(16), nullable=False)
    tier: Mapped[str] = mapped_column(String(8), nullable=False)
    case_id: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    expected: Mapped[dict | list | str | float | None] = mapped_column(JSON, nullable=True)
    actual: Mapped[dict | list | str | float | None] = mapped_column(JSON, nullable=True)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("0"))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ModelBreaker(Base):
    __tablename__ = "model_breaker"

    model_key: Mapped[str] = mapped_column(String(40), primary_key=True)
    state: Mapped[str] = mapped_column(String(8), nullable=False, default="closed")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    changed_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # [{state, reason, by, at, run_id}]
```

In `services/api/app/models/__init__.py` add the import after the `fund` line and the names to `__all__`:

```python
from app.models.governance import (BREAKER_STATES, CASE_OUTCOMES, EVAL_TIERS, EVAL_TRIGGERS, RUN_STATES, SUITE_KINDS,
                                   EvalCase, EvalRun, ModelBreaker)
```

```python
    "BREAKER_STATES", "CASE_OUTCOMES", "EVAL_TIERS", "EVAL_TRIGGERS", "RUN_STATES", "SUITE_KINDS", "EvalCase",
    "EvalRun", "ModelBreaker",
```

```python
# file: services/api/app/governance/__init__.py
"""Model governance in the manner of the Federal Reserve's SR 11-7: an inventory of every model, validation before
and after deploys, a red team, fair-lending checks, monitoring against people's decisions, and circuit breakers."""
```

```python
# file: services/api/app/governance/inventory.py
"""The model inventory: every AI and quantitative model in Atrium, once, with what governs it.

A model's version is a short hash of the text that defines it (prompt templates, schemas, rules, committed model
files) and the model id it runs on, so any change to a prompt or a rule shows as a new version without anyone
having to remember to bump a number.
"""
import hashlib
import importlib
import inspect
import json
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings

APP_ROOT = Path(__file__).resolve().parents[1]  # services/api/app
KINDS = {"gemini_prompt": "Gemini prompt", "adk_agent": "ADK agent", "bigquery_ml": "BigQuery ML",
         "document_ai": "Document AI", "rules": "Rules"}
TIERS = ("high", "medium")


@dataclass(frozen=True)
class ModelSpec:
    key: str
    name: str
    kind: str
    tier: str
    owner: str  # the owning persona's email
    purpose: str
    human_gate: str
    fallback: str | None  # what runs while the breaker is open; None when nothing can stand in
    limitations: tuple[str, ...]
    sources: tuple[str, ...]  # "module:pkg.mod", "attr:pkg.mod:NAME" or "file:path/under/app"
    model_setting: str | None = None  # the Settings attribute naming the model id it runs on


DANIEL, MEI, OMAR = "daniel@atrium.demo", "mei@atrium.demo", "omar@atrium.demo"

MODELS: dict[str, ModelSpec] = {m.key: m for m in (
    ModelSpec("lead_score", "Lead Score", "bigquery_ml", "medium", DANIEL,
              "Ranks new leads by how likely they are to become clients, with the factors for and against.",
              "An advisor decides whom to call.", None,
              ("Trained on synthetic lead history, not on real outcomes.",
               "Goal fit comes from Gemini's reading of the lead, so the enrichment's errors reach the score."),
              ("file:ml/lead_model.json", "attr:app.ml.lead_features:features_for")),
    ModelSpec("lead_enrichment", "Lead enrichment", "gemini_prompt", "medium", DANIEL,
              "Reads a lead's form and notes into goals, suggested funds, inconsistencies and a next step.",
              "An advisor reads it before calling.", "Offline rules read the form instead.",
              ("Reads only what the lead wrote; it cannot check that it is true.",),
              ("attr:app.services.enrichment:PROMPT", "attr:app.services.enrichment:Enrichment"),
              "gemini_flash_model"),
    ModelSpec("trust_rules", "Trust Score stage 1", "rules", "high", DANIEL,
              "Scores fraud and identity risk at the lead stage from contact details, devices and documents.",
              "An advisor reviews; a blocking signal stops conversion.", None,
              ("Throwaway email domains are recognised from a fixed list.",
               "A device ring is seen only when the leads share a device id."),
              ("module:app.services.trust",)),
    ModelSpec("identity_proofing", "Identity check", "document_ai", "high", DANIEL,
              "Reads an identity document and checks it against the form and Document AI's fraud signals.",
              "An advisor reviews every finding.", None,
              ("Specimen cards only in this demo; no live identity documents are read.",),
              ("module:app.services.identity",), "docai_proofing_processor"),
    ModelSpec("draft_compliance", "Draft compliance check", "gemini_prompt", "high", OMAR,
              "Flags promissory or misleading language in client messages before an advisor sends them.",
              "The advisor edits and sends.", "The rules alone check the draft.",
              ("Rules catch known phrasings; Gemini covers the rest and can miss subtle claims.",),
              ("module:app.services.compliance",), "gemini_flash_model"),
    ModelSpec("statement_reader", "Statement reading", "document_ai", "high", MEI,
              "Reads bank statement PDFs into dated lines with amounts and sides.",
              "Operations decides every match.", "Statements are read as CSV only.",
              ("The parser labels some cells inconsistently; the side is taken from the narration and the lines are "
               "checked against the balances.",),
              ("attr:app.services.statements:extraction_from_document", "attr:app.services.statements:parse_csv"),
              "docai_statement_processor"),
    ModelSpec("narration_reader", "Narration reading", "gemini_prompt", "medium", MEI,
              "Reads each statement narration into a remitter name and a payment reference.",
              "Operations decides every match.", "Rules read the narrations.",
              ("A reference with several typos can be read as no reference.",),
              ("attr:app.services.statements:NORMALISE_PROMPT", "attr:app.services.statements:StatementReading"),
              "gemini_flash_model"),
    ModelSpec("reconciler_agent", "Reconciliation agent", "adk_agent", "high", MEI,
              "Proposes matches between deposits and waiting subscriptions that the rules could not settle.",
              "Operations accepts or rejects each proposal.", "The scorer proposes the strongest matches.",
              ("It proposes; it never matches. Split payments are found only among the open lines.",),
              ("module:app.agents.reconciler", "attr:app.services.reconciliation:score"), "gemini_flash_model"),
    ModelSpec("aml_scenarios", "AML scenarios", "rules", "high", OMAR,
              "Seven monitoring scenarios adapted to US practice, from structuring to linked round trips.",
              "The MLRO decides every alert.", None,
              ("Thresholds are fixed; amounts just outside them are not flagged by the rules.",),
              ("module:app.services.aml",)),
    ModelSpec("aml_anomaly", "AML anomaly model", "bigquery_ml", "medium", OMAR,
              "A k-means model trained in BigQuery ML that flags accounts unlike their peers.",
              "The MLRO decides every alert.", "The scenarios alone raise alerts.",
              ("Trained on synthetic account behaviour.",),
              ("file:ml/aml_model.json", "attr:app.ml.aml_model:AmlModel")),
    ModelSpec("case_reviewer", "Case review", "gemini_prompt", "high", OMAR,
              "Suggests a triage, a case narrative citing the evidence, and questions for one alert.",
              "The MLRO decides.", "Case reviews pause; the MLRO decides from the evidence.",
              ("It may cite only evidence ids it was given; uncited claims are dropped.",),
              ("attr:app.services.compliance_ai:REVIEW_PROMPT", "attr:app.services.compliance_ai:AlertReview"),
              "gemini_pro_model"),
    ModelSpec("pretrade_guardian", "Pre-trade Guardian", "rules", "high", DANIEL,
              "Checks every order for suitability, concentration, liquidity, size, wash sales and takeover risk.",
              "The investor decides; an advisor decides on held orders.", "The rules run without the explanation.",
              ("Uses the latest quote; a fast market can move past it.",),
              ("module:app.services.guardian", "attr:app.services.order_ai:explain_order"), "gemini_flash_model"),
    ModelSpec("held_order_reviewer", "Held-order review note", "gemini_prompt", "medium", DANIEL,
              "Writes the advisor's review note on an order the Guardian held.",
              "The advisor releases or rejects the order.", "Review notes pause.",
              ("It sees the order and the account, not the client's circumstances beyond them.",),
              ("attr:app.services.order_ai:REVIEW_PROMPT", "attr:app.services.order_ai:ReviewNote"),
              "gemini_pro_model"),
    ModelSpec("investor_copilot", "Investor Copilot", "adk_agent", "medium", DANIEL,
              "Answers an investor's questions from their own portfolio, the engines and the fund documents.",
              "The investor decides; it never places an order.", "The Copilot pauses.",
              ("Answers only from its tools and the fund documents.",),
              ("module:app.agents.investor",), "gemini_flash_model"),
    ModelSpec("proposal_writer", "Proposal", "gemini_prompt", "medium", DANIEL,
              "Writes a personalised proposal whose every figure comes from the engines.",
              "The advisor reviews and sends it.", "Proposals pause.",
              ("Figures not found in the engines' output are flagged, not removed.",),
              ("attr:app.services.proposal:PROMPT",), "gemini_pro_model"),
    ModelSpec("scenario_mapper", "Scenario mapping", "gemini_prompt", "medium", DANIEL,
              "Turns a scenario written in plain English into explicit, bounded shocks, grounded with Google Search.",
              "The investor sees every shock and can change it.", "Only the history replays are offered.",
              ("Shocks are judgements, not forecasts; the engine's arithmetic is exact, the shocks are not.",),
              ("module:app.services.scenarios",), "gemini_flash_model"),
    ModelSpec("call_analyst", "Call analysis", "gemini_prompt", "high", DANIEL,
              "Turns a recorded client call into a transcript, a summary, proposed lead updates and conduct flags.",
              "The advisor applies each update; flags go to the advisor and compliance.", "Call analysis pauses.",
              ("A flag whose quote is not in the transcript is dropped, so a misheard quote can hide a real issue.",),
              ("module:app.services.calls",), "gemini_flash_model"),
    ModelSpec("ring_narrator", "Ring narrative", "gemini_prompt", "medium", OMAR,
              "Explains how a fraud ring's members connect and what pattern it resembles.",
              "The MLRO decides whether to open a case.", "Rings show without a narrative.",
              ("It explains links the graph found; it cannot find new ones.",),
              ("module:app.services.rings",), "gemini_flash_model"),
)}


def _source_text(source: str) -> str:
    kind, _, ref = source.partition(":")
    try:
        if kind == "file":
            return (APP_ROOT / ref).read_text(encoding="utf-8")
        if kind == "module":
            return inspect.getsource(importlib.import_module(ref))
        if kind == "attr":
            module, _, name = ref.rpartition(":")
            value = getattr(importlib.import_module(module), name)
            if isinstance(value, str):
                return value
            if hasattr(value, "model_json_schema"):
                return json.dumps(value.model_json_schema(), sort_keys=True)
            return inspect.getsource(value)
    except (ImportError, AttributeError, OSError, TypeError):
        return f"missing {source}"
    raise ValueError(f"Unknown source kind in {source!r}")


def model_id(spec: ModelSpec) -> str | None:
    return getattr(get_settings(), spec.model_setting, None) if spec.model_setting else None


def version(spec: ModelSpec) -> str:
    digest = hashlib.sha256()
    for source in spec.sources:
        digest.update(f"{source}\0{_source_text(source)}\0".encode())
    digest.update((model_id(spec) or "").encode())
    return digest.hexdigest()[:10]


def versions() -> dict[str, str]:
    return {key: version(spec) for key, spec in MODELS.items()}


def missing_sources(spec: ModelSpec) -> list[str]:
    return [s for s in spec.sources if _source_text(s) == f"missing {s}"]
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd services/api && uv run pytest -q -p no:warnings tests/test_governance.py`
Expected: PASS (3 tests). If a built model's source is missing, fix the source string to the real name in that module (read the module), never the test.

- [ ] **Step 5: Commit**

```bash
git add services/api/app/models/governance.py services/api/app/models/__init__.py services/api/app/governance services/api/tests/test_governance.py
git commit -m "feat(governance): the model inventory and the governance tables"
```

### Task F2: Circuit breakers

**Files:**
- Create: `services/api/app/governance/breakers.py`
- Test: `services/api/tests/test_governance.py` (append)

**Interfaces:**
- Consumes: `MODELS` (F1), `ModelBreaker` (F1), `verify_code` (`app.services.approvals`), `record_decision`, `emit`.
- Produces: `breaker_open`, `breaker_message`, `ensure_closed`, `trip`, `reset`, `BreakerOpen`, `BreakerError`.

- [ ] **Step 1: Append the failing tests**

```python
# (append to services/api/tests/test_governance.py)
from app.governance.breakers import BreakerError, BreakerOpen, breaker_message, breaker_open, ensure_closed, reset, trip
from app.models import AIDecision, ModelBreaker, Person

NOW = datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)


@pytest.fixture()
def omar(db):
    person = Person(kind="compliance", full_name="Omar Haddad", email="omar@atrium.demo", totp_secret="MFRGGZDFMZTWQ2LK")
    db.add(person)
    db.commit()
    return person


def test_a_breaker_is_closed_until_tripped_and_says_why_when_open(db):
    assert breaker_open(db, "case_reviewer") is False and breaker_message(db, "case_reviewer") is None
    ensure_closed(db, "case_reviewer")
    trip(db, "case_reviewer", reason="It missed its bar in the live checks.", by="Live checks", now=NOW)
    db.flush()
    assert breaker_open(db, "case_reviewer") is True
    assert breaker_message(db, "case_reviewer") == "Case review is paused: It missed its bar in the live checks. Since Oct 14."
    with pytest.raises(BreakerOpen) as raised:
        ensure_closed(db, "case_reviewer")
    assert raised.value.key == "case_reviewer" and "paused" in str(raised.value)
    trip(db, "case_reviewer", reason="A second reason.", by="Omar Haddad", now=NOW)
    assert db.get(ModelBreaker, "case_reviewer").reason == "It missed its bar in the live checks."  # the first stays


def test_resetting_needs_a_reason_and_the_current_code(db, omar):
    trip(db, "reconciler_agent", reason="Kill switch for the demo.", by="Omar Haddad", now=NOW)
    with pytest.raises(BreakerError, match="code"):
        reset(db, "reconciler_agent", reason="Fixed.", person=omar, code="000000", now=NOW)
    with pytest.raises(BreakerError, match="reason"):
        reset(db, "reconciler_agent", reason="  ", person=omar, code=pyotp.TOTP(omar.totp_secret).at(NOW), now=NOW)
    row = reset(db, "reconciler_agent", reason="The prompt was fixed and revalidated.", person=omar,
                code=pyotp.TOTP(omar.totp_secret).at(NOW), now=NOW)
    assert row.state == "closed" and [h["state"] for h in row.history] == ["open", "closed"]
    assert breaker_open(db, "reconciler_agent") is False
    purposes = set(db.scalars(select(AIDecision.purpose)).all())
    assert {"breaker_open", "breaker_reset"} <= purposes
    with pytest.raises(BreakerError, match="not paused"):
        reset(db, "reconciler_agent", reason="Again.", person=omar, code=pyotp.TOTP(omar.totp_secret).at(NOW), now=NOW)
    with pytest.raises(BreakerError, match="no model"):
        trip(db, "made_up", reason="x", by="y", now=NOW)


def test_an_unreadable_breaker_counts_as_open(db, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(db, "get", broken)
    assert breaker_open(db, "case_reviewer") is True
    assert "cannot be checked" in breaker_message(db, "case_reviewer")
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd services/api && uv run pytest -q -p no:warnings tests/test_governance.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.governance.breakers'`.

- [ ] **Step 3: Write the breakers**

```python
# file: services/api/app/governance/breakers.py
"""Circuit breakers: a model that fails validation, or that people stop agreeing with, is switched off, and its feature
falls back to its deterministic part until a compliance person resets it with a reason and a one-time code.

Checks fail to the fallback, never to the model: if the breaker table cannot be read, the breaker counts as open.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.ai.decisions import record_decision
from app.ai.llm import LLMResult
from app.events import emit
from app.governance.inventory import MODELS
from app.models import ModelBreaker, Person
from app.models.base import utcnow
from app.services.approvals import verify_code


class BreakerError(ValueError):
    """A breaker change that cannot be made: an unknown model, no reason, a wrong code, nothing to reset."""


class BreakerOpen(RuntimeError):
    """Raised by a feature whose model is switched off; the message is what the page shows."""

    def __init__(self, key: str, message: str):
        super().__init__(message)
        self.key = key


def _row(db: Session, key: str) -> ModelBreaker | None:
    return db.get(ModelBreaker, key)


def breaker_open(db: Session, key: str) -> bool:
    try:
        row = _row(db, key)
    except Exception:  # unreadable: take the fallback, never the model
        return True
    return row is not None and row.state == "open"


def _day(moment: datetime) -> str:
    return f"{moment:%b} {moment.day}"


def breaker_message(db: Session, key: str) -> str | None:
    name = MODELS[key].name
    try:
        row = _row(db, key)
    except Exception:
        return f"{name} is paused while its safety switch cannot be checked."
    if row is None or row.state != "open":
        return None
    return f"{name} is paused: {row.reason} Since {_day(row.changed_at)}."


def ensure_closed(db: Session, key: str) -> None:
    message = breaker_message(db, key)
    if message:
        raise BreakerOpen(key, message)


def _change(db: Session, key: str, state: str, reason: str, by: str, now: datetime,
            run_id: str | None) -> ModelBreaker:
    row = db.get(ModelBreaker, key)
    if row is None:
        row = ModelBreaker(model_key=key, state="closed", reason="", changed_by="", changed_at=now, history=[])
        db.add(row)
    row.state, row.reason, row.changed_by, row.changed_at, row.run_id = state, reason, by, now, run_id
    row.history = [*(row.history or []), {"state": state, "reason": reason, "by": by, "at": now.isoformat(),
                                          "run_id": run_id}]
    db.flush()
    purpose = "breaker_open" if state == "open" else "breaker_reset"
    record_decision(db, agent="governance", purpose=purpose,
                    result=LLMResult(parsed={"model": key, "state": state, "reason": reason, "by": by,
                                             "run_id": run_id},
                                     model="rules", tokens_in=0, tokens_out=0, latency_ms=0, cost_usd=0.0),
                    subject_type="model", subject_id=key, input_text=reason)
    emit("BreakerOpened" if state == "open" else "BreakerReset", {"model": key, "by": by, "run_id": run_id})
    return row


def _checked(key: str, reason: str) -> str:
    if key not in MODELS:
        raise BreakerError(f"Atrium has no model called {key}.")
    reason = (reason or "").strip()
    if not reason:
        raise BreakerError("Give a reason; it is kept in the model's history.")
    return reason


def trip(db: Session, key: str, *, reason: str, by: str, now: datetime | None = None,
         run_id: str | None = None) -> ModelBreaker:
    """Open a breaker. An already open breaker keeps its first reason."""
    reason = _checked(key, reason)
    row = db.get(ModelBreaker, key)
    if row is not None and row.state == "open":
        return row
    return _change(db, key, "open", reason, by, now or utcnow(), run_id)


def reset(db: Session, key: str, *, reason: str, person: Person, code: str,
          now: datetime | None = None) -> ModelBreaker:
    reason = _checked(key, reason)
    now = now or utcnow()
    row = db.get(ModelBreaker, key)
    if row is None or row.state != "open":
        raise BreakerError(f"{MODELS[key].name} is not paused.")
    if not verify_code(person, code, now):
        raise BreakerError("That code is not right. Use the current code from your authenticator.")
    return _change(db, key, "closed", reason, person.full_name, now, None)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd services/api && uv run pytest -q -p no:warnings tests/test_governance.py`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add services/api/app/governance/breakers.py services/api/tests/test_governance.py
git commit -m "feat(governance): circuit breakers that fail to the fallback and reset with a code"
```

### Task F3: The evaluation framework, runner and deploy-gate CLI

**Files:**
- Create: `services/api/app/governance/evals/__init__.py`, `framework.py`, `runner.py`, `__main__.py`, `suites/__init__.py`, `suites/lead_score.py`
- Test: `services/api/tests/test_governance.py` (append), `services/api/tests/test_governance_gate.py`

**Interfaces:**
- Consumes: `MODELS`, `versions` (F1), `trip`, `breaker_open` (F2), `record_decision`, `emit`, `current_bus`, `set_event_bus`, `InProcessEventBus`, `LeadModel`, `auc`, `generate_lead_history`.
- Produces: everything listed under "Shared interfaces" for `app.governance.evals.framework`, plus `app.governance.evals.runner`: `RunReport`, `run_evals(tier, *, llm=None, agent_model=None, with_documents=False, only=None, now=None) -> RunReport`, `start_run(db, *, tier, trigger, requested_by=None, now=None) -> EvalRun`, `adopt_or_start(db, *, tier, trigger, now=None) -> EvalRun`, `store_run(db, report, run, *, now=None) -> list[str]` (tripped keys), `finish_failed(db, run, error, *, now=None)`, `run_blocker(db, now=None) -> str | None`, `run_state(run, now=None) -> str` ("running", "finished", "failed", "did_not_finish"), `RUN_TIMEOUT`, `COOLDOWN`, `summarise(report) -> dict`.

- [ ] **Step 1: Append the failing tests**

```python
# (append to services/api/tests/test_governance.py)
from app.events import current_bus, emit
from app.governance.evals import framework
from app.governance.evals.framework import (CaseResult, SuiteResult, every_case, rate, run_case, scratch_db,
                                            share_passing, suite)
from app.governance.evals.runner import (COOLDOWN, RUN_TIMEOUT, adopt_or_start, finish_failed, run_blocker, run_evals,
                                         run_state, start_run, store_run)
from app.models import EvalCase, EvalRun


@pytest.fixture()
def registry():
    """Suites registered by a test never outlive it."""
    saved = list(framework.SUITES)
    yield
    framework.SUITES[:] = saved


def test_a_scratch_database_is_separate_from_the_live_one(db):
    with scratch_db() as scratch:
        scratch.add(Person(kind="investor", full_name="Scratch Only", email="scratch@example.test"))
        scratch.commit()
        assert scratch.scalar(select(Person.full_name)) == "Scratch Only"
    assert db.scalar(select(Person.full_name)) is None


def test_an_unreachable_model_is_an_error_not_a_fail():
    from app.ai.llm import LLMError

    def check():
        raise LLMError("quota")

    result = run_case("c1", check)
    assert result.outcome == "error" and "could not be reached" in result.detail
    assert share_passing([result]) is None
    assert share_passing([result, CaseResult("c2", "pass"), CaseResult("c3", "fail")]) == 0.5
    judged = rate("case_reviewer", "golden", "live", [result], bar="b", metric="m", value=None, threshold=0.8)
    assert judged.passed is False and judged.metric.startswith("No result")
    assert every_case("lead_score", "golden", "free", [CaseResult("a", "pass")], bar="b").passed is True
    assert every_case("lead_score", "golden", "free", [], bar="b").passed is False


def test_a_run_trips_only_high_risk_models_with_a_fallback_that_missed_their_bar(db, registry):
    @suite("case_reviewer", tier="live")
    def failing_high(ctx):
        emit("SomethingInsideACase", {"x": 1})  # must not reach the live event stream
        return SuiteResult("case_reviewer", "golden", "live", "bar", "2 of 5", False,
                           [CaseResult("a", "fail"), CaseResult("b", "pass")])

    @suite("lead_enrichment", tier="live")
    def failing_medium(ctx):
        return SuiteResult("lead_enrichment", "golden", "live", "bar", "1 of 2", False, [CaseResult("a", "fail")])

    @suite("reconciler_agent", tier="live")
    def all_errors(ctx):
        return SuiteResult("reconciler_agent", "golden", "live", "bar", "No result", False, [CaseResult("a", "error")])

    @suite("narration_reader", tier="live")
    def crashes(ctx):
        raise RuntimeError("boom")

    outer = current_bus()
    report = run_evals("live", only={"case_reviewer", "lead_enrichment", "reconciler_agent", "narration_reader"})
    assert "SomethingInsideACase" not in [e.type for e in outer.history]
    crashed = next(s for s in report.suites if s.model_key == "narration_reader")
    assert crashed.passed is False and crashed.cases[0].outcome == "error" and "boom" in crashed.cases[0].detail
    run = start_run(db, tier="live", trigger="deploy", now=NOW)
    tripped = store_run(db, report, run, now=NOW)
    assert tripped == ["case_reviewer"]
    assert breaker_open(db, "case_reviewer") and not breaker_open(db, "lead_enrichment")
    assert not breaker_open(db, "reconciler_agent")  # every case errored: nothing was learned
    assert run.status == "finished" and run.summary["counts"] == {"suites": 4, "passed": 0}
    assert db.scalar(select(EvalCase.case_id).where(EvalCase.model_key == "case_reviewer", EvalCase.outcome == "fail")) == "a"
    assert run.models["case_reviewer"] == versions()["case_reviewer"]


def test_free_suites_also_run_in_a_live_run_but_live_suites_never_run_free(registry):
    calls = []

    @suite("lead_score", kind="fairness")
    def free_one(ctx):
        calls.append(("free", ctx.llm))
        return SuiteResult("lead_score", "fairness", "free", "b", "m", True, [CaseResult("a", "pass")])

    @suite("lead_enrichment", tier="live")
    def live_one(ctx):
        calls.append(("live", ctx.llm))
        return SuiteResult("lead_enrichment", "golden", "live", "b", "m", True, [CaseResult("a", "pass")])

    run_evals("free", only={"lead_score", "lead_enrichment"}, llm="LLM")
    assert ("live", "LLM") not in calls and ("free", None) in calls
    calls.clear()
    run_evals("live", only={"lead_score", "lead_enrichment"}, llm="LLM")
    assert ("free", None) in calls and ("live", "LLM") in calls


def test_the_button_waits_for_a_running_run_and_for_the_cooldown(db):
    assert run_blocker(db, now=NOW) is None
    run = start_run(db, tier="live", trigger="deploy", now=NOW)
    db.flush()
    assert "still going" in run_blocker(db, now=NOW + timedelta(minutes=3))
    assert run_state(run, now=NOW + RUN_TIMEOUT + timedelta(minutes=1)) == "did_not_finish"
    assert run_blocker(db, now=NOW + RUN_TIMEOUT + timedelta(minutes=1)) is None
    finish_failed(db, run, RuntimeError("x"), now=NOW + timedelta(minutes=2))
    assert run.status == "failed" and run_blocker(db, now=NOW + timedelta(minutes=5)) is None
    done = start_run(db, tier="live", trigger="deploy", now=NOW + timedelta(hours=1))
    done.status, done.finished_at = "finished", NOW + timedelta(hours=1, minutes=5)
    db.flush()
    assert "next can start" in run_blocker(db, now=NOW + timedelta(hours=1, minutes=20))
    assert run_blocker(db, now=NOW + timedelta(hours=1, minutes=5) + COOLDOWN) is None


def test_the_job_adopts_the_run_the_button_asked_for(db):
    asked = start_run(db, tier="live", trigger="button", requested_by="Omar Haddad", now=NOW)
    db.flush()
    assert adopt_or_start(db, tier="live", trigger="deploy", now=NOW + timedelta(minutes=2)).id == asked.id
    other = adopt_or_start(db, tier="live", trigger="deploy", now=NOW + timedelta(minutes=30))
    assert other.id != asked.id and other.trigger == "deploy"
```

```python
# file: services/api/tests/test_governance_gate.py
"""The deploy gate: every free-tier suite passes on the committed code. Each feature's golden sets are covered here
automatically, because suites register themselves."""
from app.governance.evals.__main__ import main
from app.governance.evals.runner import run_evals


def test_every_free_suite_passes():
    report = run_evals("free")
    assert report.suites, "no suites were found"
    failures = [(s.model_key, s.kind, s.metric, [(c.case_id, c.outcome, c.detail) for c in s.cases if c.outcome != "pass"])
                for s in report.failures()]
    assert failures == []


def test_the_gate_exits_zero_when_everything_passes(capsys):
    assert main(["--tier", "free"]) == 0
    assert "suites passed" in capsys.readouterr().out
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd services/api && uv run pytest -q -p no:warnings tests/test_governance.py tests/test_governance_gate.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.governance.evals'`.

- [ ] **Step 3: Write the framework, the runner, the CLI and the first suite**

```python
# file: services/api/app/governance/evals/__init__.py
"""Evaluation suites for every model in the inventory, a runner that stores their results, and the deploy gate."""
```

```python
# file: services/api/app/governance/evals/suites/__init__.py
"""One module per model key. Each registers its suites with @suite; load_suites() imports every module here."""
```

```python
# file: services/api/app/governance/evals/framework.py
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
    """A suite that passes only when every case passes."""
    good = sum(c.outcome == "pass" for c in cases)
    return SuiteResult(model_key, kind, tier, bar, f"{good} of {len(cases)} cases passed",
                       bool(cases) and good == len(cases), cases)
```

```python
# file: services/api/app/governance/evals/runner.py
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


def adopt_or_start(db: Session, *, tier: str, trigger: str, now: datetime | None = None) -> EvalRun:
    """The job takes over a run the button asked for in the last ten minutes; otherwise it starts its own."""
    now = now or utcnow()
    asked = db.scalars(select(EvalRun).where(EvalRun.status == "running", EvalRun.trigger == "button",
                                             EvalRun.started_at >= now - timedelta(minutes=10))
                       .order_by(EvalRun.started_at.desc())).first()
    return asked or start_run(db, tier=tier, trigger=trigger, now=now)


def summarise(report: RunReport) -> dict:
    return {"passed": report.passed,
            "counts": {"suites": len(report.suites), "passed": sum(s.passed for s in report.suites)},
            "suites": [{"model_key": s.model_key, "kind": s.kind, "tier": s.tier, "bar": s.bar, "metric": s.metric,
                        "passed": s.passed, "counts": s.counts, "cost_usd": s.cost_usd} for s in report.suites]}


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
```

```python
# file: services/api/app/governance/evals/__main__.py
"""Run the evaluation suites.

  uv run python -m app.governance.evals --tier free           the deploy gate: free suites only, exit 1 on a failure
  python -m app.governance.evals --tier live --store          the atrium-evals job: every suite, results stored
"""
import argparse
import sys

from app.governance.evals.runner import RunReport, adopt_or_start, finish_failed, run_evals, store_run


def print_report(report: RunReport) -> None:
    for s in report.suites:
        print(f"{'PASS' if s.passed else 'FAIL'}  {s.model_key:<20} {s.kind:<10} {s.tier:<4}  {s.metric}  (bar: {s.bar})")
        for c in s.cases:
            if c.outcome != "pass":
                print(f"        {c.outcome:<5} {c.case_id}: {c.detail[:160]}")
    print(f"{sum(s.passed for s in report.suites)} of {len(report.suites)} suites passed; "
          f"AI cost ${report.cost_usd:.4f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.governance.evals")
    parser.add_argument("--tier", choices=("free", "live"), default="free")
    parser.add_argument("--store", action="store_true", help="store the results in the database")
    parser.add_argument("--trigger", choices=("deploy", "button", "local"), default="local")
    parser.add_argument("--with-documents", action="store_true", help="include Document AI reads (costs $0.20)")
    args = parser.parse_args(argv)
    if not args.store:
        if args.tier == "live":
            parser.error("live runs store their results: add --store")
        report = run_evals("free")
        print_report(report)
        return 0 if report.passed else 1
    from app.db import SessionLocal, init_db

    init_db()
    with SessionLocal() as db:
        run = adopt_or_start(db, tier=args.tier, trigger=args.trigger)
        db.commit()
        try:
            llm = agent_model = None
            if args.tier == "live":
                from app.agents.runtime import get_agent_model
                from app.ai.llm import get_llm

                llm, agent_model = get_llm(), get_agent_model()
            report = run_evals(args.tier, llm=llm, agent_model=agent_model, with_documents=args.with_documents)
            store_run(db, report, run)
            db.commit()
        except Exception as e:
            db.rollback()
            finish_failed(db, run, e)
            db.commit()
            raise
    print_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

```python
# file: services/api/app/governance/evals/suites/lead_score.py
"""Lead Score: the committed BigQuery ML model scored on synthetic leads it has never seen."""
from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, rate, suite
from app.ml.lead_history import generate_lead_history
from app.ml.lead_model import LeadModel, auc

HOLDOUT_SEED, HOLDOUT_SIZE, AUC_BAR = 2026, 400, 0.75


@suite("lead_score")
def holdout_auc(ctx: EvalContext) -> SuiteResult:
    model = LeadModel.load()
    rows = generate_lead_history(n=HOLDOUT_SIZE, seed=HOLDOUT_SEED)  # training used seed 7
    labels = [r["converted"] for r in rows]
    scores = [model.probability({k: v for k, v in r.items() if k != "converted"}) for r in rows]
    value = auc(labels, scores)
    case = CaseResult("holdout-auc", "pass" if value >= AUC_BAR else "fail", expected=f"AUC at least {AUC_BAR}",
                      actual=round(value, 4), detail=f"{HOLDOUT_SIZE} synthetic leads from seed {HOLDOUT_SEED}")
    return rate("lead_score", "golden", "free", [case], bar=f"AUC at least {AUC_BAR} on {HOLDOUT_SIZE} held-out leads",
                metric=f"AUC {value:.2f} on {HOLDOUT_SIZE} held-out leads", value=value, threshold=AUC_BAR)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd services/api && uv run pytest -q -p no:warnings tests/test_governance.py tests/test_governance_gate.py`
Expected: PASS (`InProcessEventBus.history` lists every event published on that bus).

- [ ] **Step 5: Commit**

```bash
git add services/api/app/governance/evals services/api/tests/test_governance.py services/api/tests/test_governance_gate.py
git commit -m "feat(governance): the evaluation framework, the runner that stores runs and trips breakers, and the deploy gate"
```

### Task F4: The governance API, and stubs for the feature plans

**Files:**
- Create: `services/api/app/routers/governance.py`, `services/api/app/routers/scenarios.py`, `calls.py`, `rings.py`, `services/api/app/seed/calls.py`, `rings.py`
- Modify: `services/api/app/main.py` (router list), `services/api/app/seed/bootstrap.py` (top-up seeds)
- Test: `services/api/tests/test_governance_api.py`

**Interfaces:**
- Consumes: F1–F3; `require_roles`, `CurrentUser`, `get_db`; `me` from `app.routers.operations`.
- Produces:
  - `GET /governance/models` → `{"models": [ModelRow], "counts": {status: n}, "last_run": RunRow | null}` where `ModelRow = {key, name, kind, kind_label, tier, owner, status, version, validated_version, changed_since_validation, last_validated_at, last_run_id, fallback}` and `status` ∈ `validated`, `failing`, `breaker_open`, `monitored_only`, `not_validated`, `no_result`.
  - `GET /governance/models/{key}` → `ModelRow` plus `{purpose, human_gate, limitations, sources_missing, suites: [{kind, tier, bar, metric, passed, counts, cost_usd, cases: [{case_id, outcome, expected, actual, detail, cost_usd, latency_ms}]}], breaker: {state, reason, changed_by, changed_at, history, message}}`.
  - `POST /governance/breakers/{key}/open` `{reason}` and `POST /governance/breakers/{key}/reset` `{reason, code}` → the breaker object; 422 with the `BreakerError` text; 404 for an unknown key.
  - Helpers other plans import: `model_status(db, key, run_suites) -> str`, `run_out(run) -> dict`, `latest_runs_by_model(db) -> dict[str, EvalRun]`.

- [ ] **Step 1: Write the failing tests**

```python
# file: services/api/tests/test_governance_api.py
"""The Model Risk Office API: the inventory with statuses, each model's card, and its breaker."""
from datetime import datetime, timezone

import pyotp
import pytest

from app.governance.evals.framework import CaseResult, SuiteResult
from app.governance.evals.runner import RunReport, start_run, store_run
from app.governance.inventory import versions

OMAR, MEI = {"X-Dev-User": "omar@atrium.demo"}, {"X-Dev-User": "mei@atrium.demo"}


@pytest.fixture()
def gov(client, staff):
    return client


def test_only_compliance_sees_the_models(gov):
    assert gov.get("/governance/models", headers=MEI).status_code == 403
    body = gov.get("/governance/models", headers=OMAR).json()
    assert len(body["models"]) == 18 and body["last_run"] is None
    by_key = {m["key"]: m for m in body["models"]}
    assert by_key["lead_score"]["status"] == "not_validated"      # has a suite, never run
    assert by_key["held_order_reviewer"]["status"] == "monitored_only"  # no suite at all
    assert by_key["case_reviewer"]["owner"] == "Omar Haddad"  # the owner's name when the person exists


def test_a_stored_run_validates_or_fails_each_model(gov, db):
    report = RunReport("live", [
        SuiteResult("lead_score", "golden", "free", "AUC at least 0.75", "AUC 0.79", True, [CaseResult("auc", "pass")]),
        SuiteResult("aml_scenarios", "golden", "free", "every scenario", "6 of 7", False,
                    [CaseResult("velocity", "fail", detail="did not fire")]),
    ], versions(), datetime(2026, 10, 14, tzinfo=timezone.utc), datetime(2026, 10, 14, tzinfo=timezone.utc))
    run = start_run(db, tier="live", trigger="deploy")
    store_run(db, report, run)
    db.commit()
    by_key = {m["key"]: m for m in gov.get("/governance/models", headers=OMAR).json()["models"]}
    assert by_key["lead_score"]["status"] == "validated" and by_key["lead_score"]["changed_since_validation"] is False
    assert by_key["aml_scenarios"]["status"] == "failing"
    card = gov.get("/governance/models/aml_scenarios", headers=OMAR).json()
    assert card["suites"][0]["cases"][0] == {"case_id": "velocity", "outcome": "fail", "expected": None, "actual": None,
                                             "detail": "did not fire", "cost_usd": "0.000000", "latency_ms": 0}
    assert gov.get("/governance/models/made_up", headers=OMAR).status_code == 404


def test_a_breaker_opens_by_hand_and_resets_with_a_code(gov, staff):
    opened = gov.post("/governance/breakers/case_reviewer/open", headers=OMAR, json={"reason": "Kill switch test."})
    assert opened.status_code == 200 and opened.json()["state"] == "open"
    card = gov.get("/governance/models/case_reviewer", headers=OMAR).json()
    assert card["status"] == "breaker_open" and "paused" in card["breaker"]["message"]
    wrong = gov.post("/governance/breakers/case_reviewer/reset", headers=OMAR, json={"reason": "Fixed.", "code": "000000"})
    assert wrong.status_code == 422 and "code" in wrong.json()["detail"]
    code = pyotp.TOTP(staff["omar"].totp_secret).now()
    done = gov.post("/governance/breakers/case_reviewer/reset", headers=OMAR, json={"reason": "Fixed.", "code": code})
    assert done.status_code == 200 and done.json()["state"] == "closed"
    assert gov.post("/governance/breakers/case_reviewer/open", headers=MEI, json={"reason": "x"}).status_code == 403
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd services/api && uv run pytest -q -p no:warnings tests/test_governance_api.py`
Expected: FAIL with 404 on `/governance/models`.

- [ ] **Step 3: Write the router, the stubs, and register them**

```python
# file: services/api/app/routers/governance.py
"""The Model Risk Office (SR 11-7): the model inventory with each model's validation status, its card with the
evidence behind that status, and its circuit breaker."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_roles
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
    if not has_suites:
        return "monitored_only"
    if not run_suites:
        return "not_validated"
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
    suites = [{**s, "cases": [{"case_id": c.case_id, "outcome": c.outcome, "expected": c.expected, "actual": c.actual,
                               "detail": c.detail, "cost_usd": str(c.cost_usd), "latency_ms": c.latency_ms}
                              for c in cases if c.suite == s["kind"] and c.tier == s["tier"]]}
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


@router.post("/breakers/{key}/reset")
def reset_breaker(key: str, body: ResetIn, db: Session = Depends(get_db), user: CurrentUser = Depends(mro)):
    _known(key)
    try:
        reset(db, key, reason=body.reason, person=me(db, user), code=body.code)
    except BreakerError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    db.commit()
    return breaker_out(db, key)
```

```python
# file: services/api/app/routers/scenarios.py
"""Scenario Studio (filled by the scenarios plan)."""
from fastapi import APIRouter

router = APIRouter(tags=["scenarios"])
```

```python
# file: services/api/app/routers/calls.py
"""Call intelligence (filled by the calls plan)."""
from fastapi import APIRouter

router = APIRouter(tags=["calls"])
```

```python
# file: services/api/app/routers/rings.py
"""Fraud ring radar (filled by the rings plan)."""
from fastapi import APIRouter

router = APIRouter(tags=["rings"])
```

```python
# file: services/api/app/seed/calls.py
"""Seeds for Call intelligence (filled by the calls plan): the pressure-call lead."""
from sqlalchemy.orm import Session


def seed_call_stories(db: Session) -> bool:
    return False
```

```python
# file: services/api/app/seed/rings.py
"""Seeds for the Fraud ring radar (filled by the rings plan): the link that joins a lead ring to a client account."""
from sqlalchemy.orm import Session


def seed_ring_link(db: Session) -> bool:
    return False
```

In `services/api/app/main.py`, extend the import of router modules with `governance, scenarios, calls, rings` (read the import line at the top of the file and add the four names to it), and the tuple:

```python
    for module in (health, funds, accounts, me, leads, ai, invest, profile, insights, instructions, copilot, markets,
                   trading, operations, compliance, governance, scenarios, calls, rings):
```

In `services/api/app/seed/bootstrap.py`, in the already-seeded branch after `seed_operations`, and in the fresh branch after `seed_operations`, add:

```python
                from app.seed.calls import seed_call_stories
                from app.seed.rings import seed_ring_link

                if seed_call_stories(db):  # databases seeded before call intelligence get its lead once
                    log.info("seeded call stories")
                if seed_ring_link(db):  # and the link that joins the lead ring to a client account
                    log.info("seeded the ring link")
```

(indent to match each branch).

- [ ] **Step 4: Run the tests to see them pass, then the whole API suite**

Run: `cd services/api && uv run pytest -q -p no:warnings tests/test_governance_api.py && uv run pytest -q -p no:warnings`
Expected: PASS; the whole suite stays green.

- [ ] **Step 5: Commit**

```bash
git add services/api/app/routers services/api/app/main.py services/api/app/seed services/api/tests/test_governance_api.py
git commit -m "feat(governance): the Model Risk Office API, with stubs for scenarios, calls and rings"
```

---

## Phase I: integration (after the four feature branches merge)

### Task I1: Navigation, journeys and the front door

**Files:**
- Modify: `apps/web/src/lib/nav.ts`, `apps/web/src/lib/nav.test.ts`, `apps/web/src/lib/journeys.ts`, `apps/web/src/lib/journeys.test.ts`, `apps/web/src/app/page.tsx`, `apps/web/src/components/icons.tsx` (two icons: `models`, `rings`)

**Interfaces:**
- Consumes: pages built by the feature plans: `/compliance/models`, `/compliance/models/[key]`, `/compliance/rings`, `/investor/scenarios`, the lead page's Calls section (anchor `#calls`).

- [ ] **Step 1: Write the failing tests**

```ts
// (append to apps/web/src/lib/nav.test.ts)
describe("the advanced sections", () => {
  it("puts rings and models in the compliance rail and scenarios under Portfolio", () => {
    const compliance = WORKSPACES.compliance.sections.map((s) => s.key);
    expect(compliance).toEqual(["alerts", "rings", "models", "log"]);
    expect(sectionFor(WORKSPACES.compliance, "/compliance/models/case_reviewer")?.key).toBe("models");
    expect(sectionFor(WORKSPACES.compliance, "/compliance/rings")?.key).toBe("rings");
    const portfolio = WORKSPACES.investor.sections.find((s) => s.key === "portfolio")!;
    expect(portfolio.tabs?.map((t) => t.href)).toContain("/investor/scenarios");
    expect(sectionFor(WORKSPACES.investor, "/investor/scenarios")?.key).toBe("portfolio");
  });
});
```

```ts
// (append to apps/web/src/lib/journeys.test.ts)
describe("the advanced journey steps", () => {
  it("adds a step to each story that has a new feature", () => {
    expect(journeyFor("omar@atrium.demo")!.steps.map((s) => s.href)).toEqual(
      expect.arrayContaining(["/compliance/rings", "/compliance/models"]));
    expect(journeyFor("priya@atrium.demo")!.steps.map((s) => s.href)).toContain("/investor/scenarios");
    expect(journeyFor("daniel@atrium.demo")!.steps.some((s) => s.title === "Review a client call")).toBe(true);
  });
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd apps/web && pnpm vitest run src/lib/nav.test.ts src/lib/journeys.test.ts`
Expected: FAIL on the new describe blocks.

- [ ] **Step 3: Implement**

In `nav.ts`, compliance sections become, in order: `{ key: "alerts", label: "Alerts", href: "/compliance", icon: "alerts", also: ["/compliance/alerts"] }`, `{ key: "rings", label: "Fraud rings", href: "/compliance/rings", icon: "rings" }`, `{ key: "models", label: "Models", href: "/compliance/models", icon: "models" }`, `{ key: "log", label: "Decision log", href: "/compliance/log", icon: "log" }`. Add `"models" | "rings"` to `IconName`. Portfolio tabs become X-ray `/investor/xray`, Risk `/investor/risk`, Scenarios `/investor/scenarios`, Profile `/investor/profile`. Read `sectionFor` and confirm `/compliance/models/[key]` resolves to `models` by prefix; if `sectionFor` matches exact hrefs only, add `also: ["/compliance/models/"]`.

In `icons.tsx`, add two stroke icons in the file's existing style: `models` (a shield outline with a check) and `rings` (three small circles joined by lines).

In `journeys.ts`:
- Omar: insert after "Review an alert": `{ title: "Look at a fraud ring", detail: "See four identities and a client account joined by one device, and ask Gemini what the pattern is.", href: "/compliance/rings", action: "Open fraud rings" }`, then `{ title: "Check the models", detail: "Every model's validation, the red team's attacks, the fair-lending check and the breakers.", href: "/compliance/models", action: "Open the models", match: "^/compliance/models" }`.
- Priya: append `{ title: "Stress-test your portfolio", detail: "Replay 2008, 2020 and 2022 on what you hold, or describe your own scenario.", href: "/investor/scenarios", action: "Open scenarios" }`.
- Daniel: append `{ title: "Review a client call", detail: "Play the pressure call with Ruth Alvarez and see the flags Gemini raises, each with its timestamp.", href: "<Ruth's lead page>", action: "Open the call", match: "^/advisor/leads/" }`. The href is the advisor leads list `/advisor` if the lead id is not stable; read how the existing Daniel steps link to a lead and follow the same pattern.

In `app/page.tsx`, in the "what the AI does and never does" principles, add one line each (keep the section's existing format): governed models ("Every model is validated, attacked by a red team, checked for fair lending and switched off by a breaker when it degrades"), scenarios ("Gemini proposes the shocks; the engine computes the result, and you can change every shock"), calls ("Conduct flags quote the call and give the second they were said"), rings ("Rings are found by the graph; Gemini only explains them").

- [ ] **Step 4: Run the web checks**

Run: `cd apps/web && pnpm tsc --noEmit && pnpm lint && pnpm vitest run`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src
git commit -m "feat(web): rings and models in the compliance rail, scenarios under Portfolio, and the new journey steps"
```

### Task I2: The inventory resolves every model, and the docs

**Files:**
- Modify: `services/api/tests/test_governance.py` (`NOT_YET_BUILT = set()`), `README.md` (cost table rows from spec §10 and a short "Model Risk Office" paragraph), `docs/superpowers/plans/README.md` (a Plan 7 row)

- [ ] **Step 1:** Set `NOT_YET_BUILT = set()` in `test_governance.py`; run `cd services/api && uv run pytest -q -p no:warnings tests/test_governance.py`. Expected: PASS (every model's sources resolve now that the feature modules exist). If one fails, the feature module path differs from the inventory: fix the inventory source string.
- [ ] **Step 2:** Update `README.md` and the plans index; run `bash infra/preflight.sh`. Expected: `preflight passed`.
- [ ] **Step 3: Commit**

```bash
git add services/api/tests/test_governance.py README.md docs/superpowers/plans/README.md
git commit -m "docs: the Model Risk Office, Scenario Studio, call intelligence and fraud ring radar"
```

### Task I3: Whole-branch verification, deploy, live checks

- [ ] **Step 1:** Run `cd services/api && uv run pytest -q -p no:warnings`, `uv run python -m app.governance.evals --tier free`, and `cd apps/web && pnpm tsc --noEmit && pnpm lint && pnpm vitest run`. Expected: all green, the gate prints `N of N suites passed`.
- [ ] **Step 2:** Screenshot every new page at 390 and 1440 px against the local servers (`shoot.py` with `MSYS2_ARG_CONV_EXCL='*'`): `/compliance/models`, one model card, `/compliance/rings`, `/investor/scenarios`, a lead page's Calls section. Fix what looks wrong.
- [ ] **Step 3:** Final whole-branch review (fresh reviewer, most capable model), fix pass, then `bash infra/deploy.sh`. Expected: the gate passes inside the deploy, the API, web and `atrium-evals` job deploy, and the job starts.
- [ ] **Step 4:** Live check: the Models page shows the deploy's run with real metrics; one scenario mapped; the demo pressure call analysed; the cross-stage ring narrated. Report the measured cost of each.
