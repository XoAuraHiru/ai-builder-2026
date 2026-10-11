# Atrium Foundations (Plan 1 of 6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Atrium monorepo, core API, ledger, house-fund pricing, market data, synthetic data, auth, the investor dashboard, and a public Cloud Run deployment, so that Day 2 onward only adds pillars on top of working software.

**Architecture:** A FastAPI core API (`services/api`) owns the transactional model (people, accounts, funds, prices, append-only ledger, instructions) on SQLAlchemy 2.0, SQLite for tests and local dev and Cloud SQL for PostgreSQL on Cloud Run. A Next.js app (`apps/web`) talks to it over REST with Firebase Authentication. An in-process event bus with a Pub/Sub adapter emits domain events that later plans' agents subscribe to. Two Dockerfiles deploy both to Cloud Run with `gcloud run deploy --source`.

**Tech Stack:** Python 3.12, uv, FastAPI, SQLAlchemy 2.0, pydantic-settings, pandas, yfinance, alpaca-py, firebase-admin, google-cloud-pubsub, pg8000; Node 24, pnpm, Next.js 15 (App Router, TypeScript, Tailwind), Recharts, Vitest, Firebase JS SDK; gcloud SDK 527, Cloud Run, Cloud SQL (PostgreSQL 16), Secret Manager, Pub/Sub, GitHub Actions.

**Spec:** `docs/Atrium-Product-Blueprint.md` (v0.1, approved 11 Oct 2026). This plan implements Section 10.2 Days 0 and 1, the data model in Section 9, house funds in Section 5.3, features B2 and P1/P2/P7 from Section 5, and the repository layout in Section 8.4.

## Global Constraints

- **Fresh code only.** Every file is written during the hackathon window (spec §2.3). Never copy code or data from employer or client repositories. Domain knowledge is allowed; code is not.
- **Forbidden name.** The name of the wealth manager that inspired the investor platform must not appear anywhere: code, comments, commit messages, README, fixtures, URLs. Grep for it before every commit.
- **Markets.** US-listed equities and ETFs only; base currency `USD` (spec §4.3). No real money: Alpaca **paper** trading only (`alpaca_paper=True`).
- **No real personal data.** All people in fixtures and seeds are synthetic (spec §4.5 item 5).
- **Model IDs pinned in one place** (spec §6.3): `gemini_flash_model="gemini-3.8-flash"` (GA, released 2 Sep 2026) and `gemini_pro_model="gemini-3.1-pro-preview"`. Region `us-central1`.
- **Money maths is deterministic code, never a model** (spec §6.1 item 4). Units quantised to 6 decimal places, cash to 2, `ROUND_HALF_EVEN`.
- **Ledger is append-only** (spec §5.5 D2): postings are never updated or deleted; balances derive from postings and lots.
- **Python 3.12**, `uv` for environments; **Node 24**, `pnpm` for the web app. All code, comments and docs in English.
- **Deployment target:** Cloud Run in `us-central1`, GCP project `atrium-cup-2026` (created in Task 12), Cloud SQL instance `atrium-db`.
- **Commit convention:** Conventional Commits (`feat:`, `fix:`, `chore:`, `test:`, `docs:`), one commit per task step that says "Commit". Every commit message ends with the line `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

Inputs the spec implies but no feature description spells out. Each has a pinned test in the task named.

1. **A portfolio valued on a weekend or holiday** must use the last published price on or before that date, not fail. Pinned in Task 7 (`test_valuation_uses_last_price_on_or_before_as_of`).
2. **An account with no holdings** must return a zeroed portfolio with HTTP 200, not a 500. Pinned in Task 7 (`test_portfolio_for_empty_account_is_zero`).
3. **A fund code or account id that does not exist** must return HTTP 404 with a JSON detail. Pinned in Task 7 (`test_unknown_fund_returns_404`, `test_unknown_account_returns_404`).
4. **A malformed or missing dev-auth header** must return 401, never 500, and a user with the wrong role must get 403. Pinned in Task 10.
5. **A ticker the market data provider does not know** must raise a clear `MarketDataError` rather than returning an empty frame that silently prices a fund at NaN. Pinned in Task 6 (`test_fake_rejects_unknown_ticker_pattern`, `test_yfinance_empty_frame_raises`).

## File Structure

```
ai-builder-2026/                         repo root (already a git repo on main)
  .gitignore                             Task 1
  .github/workflows/ci.yml               Task 13
  README.md                              exists; Task 13 adds run/deploy sections
  docs/Atrium-Product-Blueprint.md       spec (exists)
  services/api/
    pyproject.toml                       Task 1   deps, pytest config, hatch build
    Dockerfile                           Task 12  python:3.12-slim + uv
    .env.example                         Task 2
    app/__init__.py                      Task 1
    app/main.py                          Task 1, revised Task 2  app factory, lifespan, routers
    app/config.py                        Task 2   Settings (pydantic-settings)
    app/db.py                            Task 2   engine, session, Base, init_db, get_db
    app/models/__init__.py               Task 3   re-exports
    app/models/base.py                   Task 3   IdMixin, new_id, utcnow
    app/models/person.py                 Task 3   Person
    app/models/account.py                Task 3   Account
    app/models/fund.py                   Task 3   Fund, FundConstituent
    app/models/price.py                  Task 3   Price
    app/models/ledger.py                 Task 3   Posting, Lot
    app/models/instruction.py            Task 3   Instruction
    app/services/ledger.py               Task 4   apply_posting, balance, holdings
    app/seed/__init__.py                 Task 5
    app/seed/funds.py                    Task 5   HOUSE_FUNDS, seed_funds
    app/services/pricing.py              Task 5   build_nav_series, publish_prices, pricing_guard, latest_price
    app/services/market_data.py          Task 6   MarketData protocol, Fake/YFinance/Alpaca, get_market_data
    app/services/portfolio.py            Task 7   valuation -> PortfolioView
    app/schemas/__init__.py              Task 7
    app/schemas/funds.py                 Task 7
    app/schemas/portfolio.py             Task 7
    app/routers/__init__.py              Task 1
    app/routers/health.py                Task 1
    app/routers/funds.py                 Task 7
    app/routers/accounts.py              Task 7, protected in Task 10
    app/seed/generate.py                 Task 8   synthetic people, accounts, instructions, postings, prices; CLI
    app/events.py                        Task 9   Event, InProcessEventBus, PubSubEventBus, get_event_bus
    app/auth.py                          Task 10  CurrentUser, get_current_user, require_roles
    tests/conftest.py                    Task 1, extended Task 3/4/7
    tests/test_health.py                 Task 1
    tests/test_config_db.py              Task 2
    tests/test_models.py                 Task 3
    tests/test_ledger.py                 Task 4
    tests/test_pricing.py                Task 5
    tests/test_market_data.py            Task 6
    tests/test_portfolio_api.py          Task 7
    tests/test_generate.py               Task 8
    tests/test_events.py                 Task 9
    tests/test_auth.py                   Task 10
  apps/web/                              Task 11  Next.js app
    Dockerfile                           Task 12
    src/lib/api.ts                       Task 11  fetch wrapper
    src/lib/allocation.ts                Task 11  pure data transforms (unit tested)
    src/lib/allocation.test.ts           Task 11
    src/lib/firebase.ts                  Task 11
    src/components/why-panel.tsx         Task 11  explain-everything shell (spec P4)
    src/components/allocation-chart.tsx  Task 11
    src/app/layout.tsx                   Task 11  role navigation shell
    src/app/page.tsx                     Task 11  redirects to /investor
    src/app/login/page.tsx               Task 11
    src/app/investor/page.tsx            Task 11  dashboard (spec B2)
  infra/
    setup_gcp.sh                         Task 12  project, APIs, Cloud SQL, secrets, SA, topic
    deploy.sh                            Task 12  gcloud run deploy for api and web
    preflight.sh                         Task 12  checks before deploy
```

Deviation from spec §8.4: the synthetic data generator and fund seed live inside the API package (`app/seed/`) so they share models and services without path hacks. `data/` at the repo root is reserved for fund fact-sheet documents (Plan 3) and the market-data cache.

---

### Task 1: Repository scaffold and API health endpoint

**Files:**
- Create: `.gitignore`
- Create: `services/api/pyproject.toml`
- Create: `services/api/app/__init__.py`
- Create: `services/api/app/main.py`
- Create: `services/api/app/routers/__init__.py`
- Create: `services/api/app/routers/health.py`
- Create: `services/api/tests/conftest.py`
- Create: `services/api/tests/test_health.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `app.main:app` (FastAPI instance) and `GET /health` returning `{"status": "ok", "service": "atrium-api"}`. Task 2 replaces `main.py` with an app factory but keeps `app` importable at module level.

- [ ] **Step 1: Create the root `.gitignore`**

```gitignore
# Python
__pycache__/
*.pyc
.venv/
*.egg-info/
.pytest_cache/
.coverage
# Local databases and caches
*.db
*.db-journal
data/cache/
# Node
node_modules/
.next/
out/
*.tsbuildinfo
# Environment
.env
.env.*
!.env.example
infra/.forbidden-words
# OS / editors
.DS_Store
Thumbs.db
.vscode/
.idea/
# Build artefacts
dist/
build/
```

- [ ] **Step 2: Create `services/api/pyproject.toml`**

```toml
[project]
name = "atrium-api"
version = "0.1.0"
description = "Atrium core API: people, accounts, house funds, prices, ledger"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "sqlalchemy>=2.0.30",
  "pydantic>=2.7",
  "pydantic-settings>=2.3",
  "pandas>=2.2",
  "numpy>=1.26",
  "yfinance>=0.2.50",
  "alpaca-py>=0.30",
  "firebase-admin>=6.5",
  "google-cloud-pubsub>=2.21",
  "pg8000>=1.31",
]

[dependency-groups]
dev = [
  "pytest>=8.2",
  "httpx>=0.27",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
markers = ["network: tests that call real market-data providers (skipped unless ATRIUM_NETWORK_TESTS=1)"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

- [ ] **Step 3: Create the empty package markers**

`services/api/app/__init__.py`:

```python
"""Atrium core API."""
```

`services/api/app/routers/__init__.py`:

```python
"""FastAPI routers."""
```

- [ ] **Step 4: Write the failing health test**

`services/api/tests/conftest.py`:

```python
import os

# Test environment is fixed before any app module is imported.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("AUTH_MODE", "dev")
os.environ.setdefault("MARKET_DATA_PROVIDER", "fake")
os.environ.setdefault("PUBSUB_ENABLED", "false")
```

`services/api/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "atrium-api"
```

- [ ] **Step 5: Install dependencies and run the test to verify it fails**

Run (from repo root):

```bash
cd services/api && uv sync && uv run pytest tests/test_health.py -v
```

Expected: `uv sync` creates `.venv` and `uv.lock`; pytest fails with `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 6: Write the minimal app and health router**

`services/api/app/routers/health.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "atrium-api"}
```

`services/api/app/main.py`:

```python
from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="Atrium API", version="0.1.0")
app.include_router(health.router)
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `cd services/api && uv run pytest tests/test_health.py -v`
Expected: `1 passed`.

- [ ] **Step 8: Commit**

```bash
git add .gitignore services/api
git commit -m "feat(api): scaffold FastAPI service with health endpoint

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Settings and database session

**Files:**
- Create: `services/api/app/config.py`
- Create: `services/api/app/db.py`
- Create: `services/api/.env.example`
- Modify: `services/api/app/main.py` (replace with app factory + lifespan)
- Modify: `services/api/app/routers/health.py` (add `env` to the body)
- Create: `services/api/tests/test_config_db.py`

**Interfaces:**
- Consumes: `app.routers.health.router` from Task 1.
- Produces:
  - `app.config.Settings` (pydantic-settings) with fields listed below and `app.config.get_settings() -> Settings` (cached).
  - `app.db.Base` (DeclarativeBase), `app.db.engine`, `app.db.SessionLocal`, `app.db.init_db() -> None`, `app.db.get_db() -> Iterator[Session]` (FastAPI dependency).
  - `app.main.create_app() -> FastAPI` and module-level `app`.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/test_config_db.py`:

```python
from sqlalchemy import text

from app.config import Settings, get_settings
from app.db import SessionLocal, engine, init_db


def test_settings_defaults_pin_models_and_region():
    s = Settings(_env_file=None)
    assert s.gemini_flash_model == "gemini-3.8-flash"
    assert s.gemini_pro_model == "gemini-3.1-pro-preview"
    assert s.gcp_location == "us-central1"
    assert s.alpaca_paper is True


def test_get_settings_reads_test_environment():
    s = get_settings()
    assert s.auth_mode == "dev"
    assert s.database_url.startswith("sqlite")


def test_init_db_and_session_round_trip():
    init_db()
    with SessionLocal() as db:
        assert db.execute(text("select 1")).scalar() == 1
    assert engine.url.get_backend_name() == "sqlite"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd services/api && uv run pytest tests/test_config_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: Write `config.py`**

`services/api/app/config.py`:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Values come from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "local"                      # local | dev | prod
    database_url: str = "sqlite+pysqlite:///./atrium.db"
    auth_mode: str = "dev"                  # dev | firebase

    gcp_project: str = ""
    gcp_location: str = "us-central1"
    gemini_flash_model: str = "gemini-3.8-flash"
    gemini_pro_model: str = "gemini-3.1-pro-preview"

    market_data_provider: str = "fake"      # fake | yfinance | alpaca
    market_cache_dir: str = "data/cache"
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper: bool = True

    pubsub_enabled: bool = False
    pubsub_topic: str = "atrium-events"

    auto_seed: bool = False                 # seed synthetic data at startup if the DB is empty
    seed: int = 42


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Write `db.py`**

`services/api/app/db.py`:

```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool  # one shared connection so tables persist across sessions
        return create_engine(url, **kwargs)
    return create_engine(url, pool_pre_ping=True)


engine: Engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables. Models register themselves on import."""
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Because `app.models` does not exist until Task 3, create a placeholder now so `init_db()` imports cleanly:

`services/api/app/models/__init__.py`:

```python
"""SQLAlchemy models. Task 3 fills this in."""
```

- [ ] **Step 5: Replace `main.py` with the app factory and extend health**

`services/api/app/main.py`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import init_db
from app.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Atrium API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health.router)
    return app


app = create_app()
```

`services/api/app/routers/health.py`:

```python
from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    return {"status": "ok", "service": "atrium-api", "env": request.app.state.settings.env}
```

- [ ] **Step 6: Create `.env.example`**

`services/api/.env.example`:

```dotenv
ENV=local
DATABASE_URL=sqlite+pysqlite:///./atrium.db
AUTH_MODE=dev
GCP_PROJECT=atrium-cup-2026
GCP_LOCATION=us-central1
GEMINI_FLASH_MODEL=gemini-3.8-flash
GEMINI_PRO_MODEL=gemini-3.1-pro-preview
MARKET_DATA_PROVIDER=fake
MARKET_CACHE_DIR=data/cache
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_PAPER=true
PUBSUB_ENABLED=false
PUBSUB_TOPIC=atrium-events
AUTO_SEED=true
SEED=42
```

- [ ] **Step 7: Run all tests to verify they pass**

Run: `cd services/api && uv run pytest -v`
Expected: `4 passed` (3 new + health; health still asserts status and service).

- [ ] **Step 8: Commit**

```bash
git add services/api
git commit -m "feat(api): settings, database session and app factory

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---
### Task 3: Domain models

**Files:**
- Create: `services/api/app/models/base.py`
- Create: `services/api/app/models/person.py`
- Create: `services/api/app/models/account.py`
- Create: `services/api/app/models/fund.py`
- Create: `services/api/app/models/price.py`
- Create: `services/api/app/models/ledger.py`
- Create: `services/api/app/models/instruction.py`
- Modify: `services/api/app/models/__init__.py` (re-export all models)
- Modify: `services/api/tests/conftest.py` (add `db` fixture)
- Create: `services/api/tests/test_models.py`

**Interfaces:**
- Consumes: `app.db.Base` from Task 2.
- Produces the SQLAlchemy models below. Later tasks use these exact attribute names:
  - `Person(id, kind, full_name, email, country, risk_band, firebase_uid, created_at)`; `kind` in `{"investor","advisor","ops","compliance","admin"}`.
  - `Account(id, person_id, number, type, status, base_currency, bank_last4, bank_verified, opened_on, created_at)`.
  - `Fund(code, name, category, risk_band, fee_bps, min_investment, objective, who_for, inception_on)` with `constituents: list[FundConstituent]`; `FundConstituent(id, fund_code, ticker, weight, asset_class, region, sector)`.
  - `Price(id, fund_code, as_of, nav, units_in_issue, status, published_at)`; unique `(fund_code, as_of)`; `status` in `{"draft","checked","published"}`.
  - `Posting(id, account_id, instrument, instrument_type, posting_type, units, cash, price, realised_cost, value_date, reference, reversal_of, created_at)`.
  - `Lot(id, account_id, instrument, units_initial, units_remaining, cost_per_unit, acquired_on, posting_id, created_at)`.
  - `Instruction(id, account_id, fund_code, type, amount, units, state, dealing_date, requested_at, settled_at, notes)`.
- Test fixture `db` (a Session on a fresh in-memory schema) for all later tests.

- [ ] **Step 1: Write the failing model test**

Append to `services/api/tests/conftest.py`:

```python
import pytest


@pytest.fixture()
def db():
    from app.db import Base, SessionLocal, engine, init_db

    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)
```

`services/api/tests/test_models.py`:

```python
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import Account, Fund, FundConstituent, Person, Price


def test_person_account_fund_price_round_trip(db):
    person = Person(kind="investor", full_name="Priya Raman", email="priya@example.test", country="US")
    db.add(person)
    db.flush()
    account = Account(person_id=person.id, number="ACC-0001", opened_on=date(2026, 1, 5))
    fund = Fund(
        code="ATR-BAL", name="Atrium Balanced", category="balanced", risk_band=3, fee_bps=35,
        min_investment=Decimal("500"), objective="Balanced growth and income.",
        who_for="Medium horizons, moderate tolerance.", inception_on=date(2024, 10, 1),
    )
    fund.constituents = [
        FundConstituent(ticker="VTI", weight=Decimal("0.6"), asset_class="equity", region="US", sector="broad"),
        FundConstituent(ticker="BND", weight=Decimal("0.4"), asset_class="bond", region="US", sector="aggregate"),
    ]
    db.add_all([account, fund])
    db.flush()
    db.add(Price(fund_code="ATR-BAL", as_of=date(2026, 1, 5), nav=Decimal("112.345678"),
                 units_in_issue=Decimal("1000000"), status="published"))
    db.commit()

    loaded = db.scalar(select(Fund).where(Fund.code == "ATR-BAL"))
    assert loaded is not None
    assert [c.ticker for c in loaded.constituents] == ["VTI", "BND"]
    assert sum(c.weight for c in loaded.constituents) == Decimal("1.0")
    assert db.scalar(select(Account).where(Account.number == "ACC-0001")).person_id == person.id
    assert db.scalar(select(Price)).nav == Decimal("112.345678")
    assert account.base_currency == "USD"
    assert account.status == "active"
    assert person.id and len(person.id) == 32
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'Account' from 'app.models'`.

- [ ] **Step 3: Write `models/base.py`**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IdMixin:
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
```

- [ ] **Step 4: Write `models/person.py` and `models/account.py`**

`services/api/app/models/person.py`:

```python
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin

PERSON_KINDS = ("investor", "advisor", "ops", "compliance", "admin")


class Person(IdMixin, Base):
    __tablename__ = "person"

    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    risk_band: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 1..5, set by onboarding (Plan 3)
    firebase_uid: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
```

`services/api/app/models/account.py`:

```python
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import IdMixin


class Account(IdMixin, Base):
    __tablename__ = "account"

    person_id: Mapped[str] = mapped_column(ForeignKey("person.id"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="individual")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    bank_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    bank_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    opened_on: Mapped[date] = mapped_column(Date, nullable=False)

    person = relationship("Person", lazy="joined")
```

- [ ] **Step 5: Write `models/fund.py` and `models/price.py`**

`services/api/app/models/fund.py`:

```python
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import IdMixin

FUND_CATEGORIES = ("money_market", "income", "balanced", "growth", "global_equity", "income_equity", "sector")


class Fund(Base):
    __tablename__ = "fund"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    risk_band: Mapped[int] = mapped_column(Integer, nullable=False)
    fee_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    min_investment: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    who_for: Mapped[str] = mapped_column(Text, nullable=False)
    inception_on: Mapped[date] = mapped_column(Date, nullable=False)

    constituents: Mapped[list["FundConstituent"]] = relationship(
        back_populates="fund", cascade="all, delete-orphan", order_by="FundConstituent.weight.desc()", lazy="selectin"
    )


class FundConstituent(IdMixin, Base):
    __tablename__ = "fund_constituent"

    fund_code: Mapped[str] = mapped_column(ForeignKey("fund.code"), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(12), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(16), nullable=False)   # equity | bond | cash
    region: Mapped[str] = mapped_column(String(16), nullable=False)        # US | DM_ex_US | EM | Global
    sector: Mapped[str] = mapped_column(String(24), nullable=False)        # broad | technology | dividend | treasury | aggregate | corporate

    fund = relationship("Fund", back_populates="constituents")
```

`services/api/app/models/price.py`:

```python
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin

PRICE_STATUSES = ("draft", "checked", "published")


class Price(IdMixin, Base):
    __tablename__ = "price"
    __table_args__ = (UniqueConstraint("fund_code", "as_of", name="uq_price_fund_asof"),)

    fund_code: Mapped[str] = mapped_column(ForeignKey("fund.code"), nullable=False, index=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    nav: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    units_in_issue: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 6: Write `models/ledger.py` and `models/instruction.py`**

`services/api/app/models/ledger.py`:

```python
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin

POSTING_TYPES = ("subscription", "redemption", "buy", "sell", "reversal", "adjustment")
INSTRUMENT_TYPES = ("fund", "equity")


class Posting(IdMixin, Base):
    """One immutable movement of units and/or cash on an account. Never updated, never deleted."""

    __tablename__ = "posting"

    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"), nullable=False, index=True)
    instrument: Mapped[str] = mapped_column(String(16), nullable=False, index=True)   # fund code or ticker
    instrument_type: Mapped[str] = mapped_column(String(8), nullable=False)
    posting_type: Mapped[str] = mapped_column(String(16), nullable=False)
    units: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)             # signed
    cash: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)              # signed, USD
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    realised_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)  # FIFO cost released by a sale
    value_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(64), nullable=False)
    reversal_of: Mapped[str | None] = mapped_column(ForeignKey("posting.id"), nullable=True)


class Lot(IdMixin, Base):
    """A tax lot opened by a positive posting and consumed FIFO by negative postings."""

    __tablename__ = "lot"

    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"), nullable=False, index=True)
    instrument: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    units_initial: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    units_remaining: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    cost_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    acquired_on: Mapped[date] = mapped_column(Date, nullable=False)
    posting_id: Mapped[str] = mapped_column(ForeignKey("posting.id"), nullable=False)
```

`services/api/app/models/instruction.py`:

```python
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin, utcnow

INSTRUCTION_TYPES = ("subscribe", "redeem", "switch")
INSTRUCTION_STATES = ("received", "accepted", "priced", "allocated", "settled", "rejected")


class Instruction(IdMixin, Base):
    __tablename__ = "instruction"

    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"), nullable=False, index=True)
    fund_code: Mapped[str] = mapped_column(ForeignKey("fund.code"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(12), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)   # cash in for subscribe
    units: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)    # units out for redeem
    state: Mapped[str] = mapped_column(String(12), nullable=False, default="received")
    dealing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 7: Re-export from `models/__init__.py`**

```python
"""SQLAlchemy models. Importing this package registers every table on Base.metadata."""

from app.models.account import Account
from app.models.fund import FUND_CATEGORIES, Fund, FundConstituent
from app.models.instruction import INSTRUCTION_STATES, INSTRUCTION_TYPES, Instruction
from app.models.ledger import INSTRUMENT_TYPES, POSTING_TYPES, Lot, Posting
from app.models.person import PERSON_KINDS, Person
from app.models.price import PRICE_STATUSES, Price

__all__ = [
    "Account", "Fund", "FundConstituent", "FUND_CATEGORIES", "Instruction", "INSTRUCTION_STATES",
    "INSTRUCTION_TYPES", "Lot", "Posting", "POSTING_TYPES", "INSTRUMENT_TYPES", "Person",
    "PERSON_KINDS", "Price", "PRICE_STATUSES",
]
```

- [ ] **Step 8: Run all tests to verify they pass**

Run: `cd services/api && uv run pytest -v`
Expected: `5 passed`.

- [ ] **Step 9: Commit**

```bash
git add services/api
git commit -m "feat(api): domain models for people, accounts, funds, prices, ledger, instructions

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Append-only ledger service with FIFO lots

**Files:**
- Create: `services/api/app/services/__init__.py`
- Create: `services/api/app/services/ledger.py`
- Modify: `services/api/tests/conftest.py` (add `account` fixture)
- Create: `services/api/tests/test_ledger.py`

**Interfaces:**
- Consumes: `Posting`, `Lot`, `Person`, `Account` from Task 3.
- Produces (all in `app.services.ledger`):
  - `q_units(Decimal) -> Decimal` (6 dp, half-even) and `q_cash(Decimal) -> Decimal` (2 dp, half-even).
  - `apply_posting(db, *, account_id: str, instrument: str, instrument_type: str, posting_type: str, units: Decimal, cash: Decimal, price: Decimal, value_date: date, reference: str) -> Posting`. Positive units open a `Lot`; negative units consume lots FIFO and set `posting.realised_cost`.
  - `balance(db, account_id: str, instrument: str) -> Decimal`.
  - `holdings(db, account_id: str) -> list[Holding]` where `Holding(instrument, instrument_type, units, cost_basis)`.
  - Exceptions `LedgerError`, `InsufficientUnits(LedgerError)`.

- [ ] **Step 1: Add the `account` fixture**

Append to `services/api/tests/conftest.py`:

```python
@pytest.fixture()
def account(db):
    from datetime import date

    from app.models import Account, Person

    person = Person(kind="investor", full_name="Priya Raman", email="priya@example.test", country="US")
    db.add(person)
    db.flush()
    acc = Account(person_id=person.id, number="ACC-0001", opened_on=date(2026, 1, 5))
    db.add(acc)
    db.commit()
    return acc
```

- [ ] **Step 2: Write the failing ledger tests**

`services/api/tests/test_ledger.py`:

```python
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Lot, Posting
from app.services.ledger import InsufficientUnits, apply_posting, balance, holdings, q_cash, q_units


def sub(db, account, units, cash, price, day, ref):
    return apply_posting(
        db, account_id=account.id, instrument="ATR-BAL", instrument_type="fund", posting_type="subscription",
        units=Decimal(units), cash=Decimal(cash), price=Decimal(price), value_date=day, reference=ref,
    )


def test_subscription_opens_lot_and_balance(db, account):
    sub(db, account, "81.012345", "-10000.00", "123.438100", date(2026, 1, 5), "SUB-1")
    assert balance(db, account.id, "ATR-BAL") == Decimal("81.012345")
    h = holdings(db, account.id)
    assert len(h) == 1
    assert h[0].instrument == "ATR-BAL"
    assert h[0].units == Decimal("81.012345")
    assert h[0].cost_basis == q_cash(Decimal("81.012345") * Decimal("123.438100"))
    lots = db.scalars(select(Lot)).all()
    assert len(lots) == 1 and lots[0].units_remaining == Decimal("81.012345")


def test_redemption_consumes_lots_fifo_and_records_realised_cost(db, account):
    sub(db, account, "100", "-1000.00", "10", date(2026, 1, 1), "SUB-1")
    sub(db, account, "100", "-1200.00", "12", date(2026, 2, 1), "SUB-2")
    red = apply_posting(
        db, account_id=account.id, instrument="ATR-BAL", instrument_type="fund", posting_type="redemption",
        units=Decimal("-150"), cash=Decimal("2250.00"), price=Decimal("15"), value_date=date(2026, 3, 1), reference="RED-1",
    )
    assert red.realised_cost == Decimal("1600.00")          # 100 @ 10 + 50 @ 12
    lots = db.scalars(select(Lot).order_by(Lot.acquired_on)).all()
    assert [l.units_remaining for l in lots] == [Decimal("0"), Decimal("50")]
    assert balance(db, account.id, "ATR-BAL") == Decimal("50")
    assert holdings(db, account.id)[0].cost_basis == Decimal("600.00")


def test_redeeming_more_than_held_raises_and_writes_nothing(db, account):
    sub(db, account, "10", "-100.00", "10", date(2026, 1, 1), "SUB-1")
    with pytest.raises(InsufficientUnits):
        apply_posting(
            db, account_id=account.id, instrument="ATR-BAL", instrument_type="fund", posting_type="redemption",
            units=Decimal("-10.000001"), cash=Decimal("100.00"), price=Decimal("10"), value_date=date(2026, 1, 2), reference="RED-X",
        )
    db.rollback()
    assert len(db.scalars(select(Posting)).all()) == 1
    assert balance(db, account.id, "ATR-BAL") == Decimal("10")


def test_quantisation_is_six_and_two_places_half_even():
    assert q_units(Decimal("1.0000005")) == Decimal("1.000000")
    assert q_units(Decimal("1.0000015")) == Decimal("1.000002")
    assert q_cash(Decimal("10.005")) == Decimal("10.00")
    assert q_cash(Decimal("10.015")) == Decimal("10.02")


def test_holdings_are_per_instrument_and_skip_zero_positions(db, account):
    sub(db, account, "5", "-500.00", "100", date(2026, 1, 1), "SUB-1")
    apply_posting(
        db, account_id=account.id, instrument="ATR-GRW", instrument_type="fund", posting_type="subscription",
        units=Decimal("2"), cash=Decimal("-300.00"), price=Decimal("150"), value_date=date(2026, 1, 1), reference="SUB-2",
    )
    apply_posting(
        db, account_id=account.id, instrument="ATR-BAL", instrument_type="fund", posting_type="redemption",
        units=Decimal("-5"), cash=Decimal("550.00"), price=Decimal("110"), value_date=date(2026, 1, 9), reference="RED-1",
    )
    h = holdings(db, account.id)
    assert [x.instrument for x in h] == ["ATR-GRW"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd services/api && uv run pytest tests/test_ledger.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services'`.

- [ ] **Step 4: Write the ledger service**

`services/api/app/services/__init__.py`:

```python
"""Domain services. Pure business logic over the models; no HTTP here."""
```

`services/api/app/services/ledger.py`:

```python
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import INSTRUMENT_TYPES, POSTING_TYPES, Lot, Posting

UNITS_Q = Decimal("0.000001")
CASH_Q = Decimal("0.01")


class LedgerError(Exception):
    pass


class InsufficientUnits(LedgerError):
    pass


def q_units(x: Decimal) -> Decimal:
    return Decimal(x).quantize(UNITS_Q, rounding=ROUND_HALF_EVEN)


def q_cash(x: Decimal) -> Decimal:
    return Decimal(x).quantize(CASH_Q, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True)
class Holding:
    instrument: str
    instrument_type: str
    units: Decimal
    cost_basis: Decimal


def balance(db: Session, account_id: str, instrument: str) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(Posting.units), 0)).where(
            Posting.account_id == account_id, Posting.instrument == instrument
        )
    )
    return q_units(Decimal(total))


def holdings(db: Session, account_id: str) -> list[Holding]:
    rows = db.execute(
        select(
            Lot.instrument,
            func.sum(Lot.units_remaining),
            func.sum(Lot.units_remaining * Lot.cost_per_unit),
        )
        .where(Lot.account_id == account_id, Lot.units_remaining > 0)
        .group_by(Lot.instrument)
        .order_by(Lot.instrument)
    ).all()
    out: list[Holding] = []
    for instrument, units, cost in rows:
        units = q_units(Decimal(units))
        if units <= 0:
            continue
        itype = db.scalar(
            select(Posting.instrument_type).where(Posting.account_id == account_id, Posting.instrument == instrument).limit(1)
        )
        posted = balance(db, account_id, instrument)
        if posted != units:
            raise LedgerError(f"lot/posting mismatch for {instrument}: lots={units} postings={posted}")
        out.append(Holding(instrument=instrument, instrument_type=itype or "fund", units=units, cost_basis=q_cash(Decimal(cost))))
    return out


def apply_posting(
    db: Session,
    *,
    account_id: str,
    instrument: str,
    instrument_type: str,
    posting_type: str,
    units: Decimal,
    cash: Decimal,
    price: Decimal,
    value_date: date,
    reference: str,
) -> Posting:
    """Append one posting. Positive units open a lot; negative units consume lots FIFO.

    Raises InsufficientUnits before anything is written if the account cannot cover a sale.
    Callers own the transaction: commit after a successful call, rollback on error.
    """
    if instrument_type not in INSTRUMENT_TYPES:
        raise LedgerError(f"unknown instrument_type {instrument_type!r}")
    if posting_type not in POSTING_TYPES:
        raise LedgerError(f"unknown posting_type {posting_type!r}")
    units = q_units(Decimal(units))
    cash = q_cash(Decimal(cash))
    price = Decimal(price)
    if units == 0 and cash == 0:
        raise LedgerError("a posting must move units or cash")

    realised_cost: Decimal | None = None
    consumed: list[tuple[Lot, Decimal]] = []
    if units < 0:
        consumed = _consume_fifo(db, account_id, instrument, -units)
        realised_cost = q_cash(sum((take * lot.cost_per_unit for lot, take in consumed), Decimal("0")))

    posting = Posting(
        account_id=account_id, instrument=instrument, instrument_type=instrument_type, posting_type=posting_type,
        units=units, cash=cash, price=price, realised_cost=realised_cost, value_date=value_date, reference=reference,
    )
    db.add(posting)
    db.flush()
    if units > 0:
        db.add(Lot(
            account_id=account_id, instrument=instrument, units_initial=units, units_remaining=units,
            cost_per_unit=price, acquired_on=value_date, posting_id=posting.id,
        ))
        db.flush()
    return posting


def _consume_fifo(db: Session, account_id: str, instrument: str, units_to_sell: Decimal) -> list[tuple[Lot, Decimal]]:
    lots = db.scalars(
        select(Lot)
        .where(Lot.account_id == account_id, Lot.instrument == instrument, Lot.units_remaining > 0)
        .order_by(Lot.acquired_on, Lot.created_at)
    ).all()
    available = q_units(sum((lot.units_remaining for lot in lots), Decimal("0")))
    if available < units_to_sell:
        raise InsufficientUnits(f"{instrument}: holding {available}, requested {units_to_sell}")
    remaining = units_to_sell
    consumed: list[tuple[Lot, Decimal]] = []
    for lot in lots:
        if remaining <= 0:
            break
        take = min(lot.units_remaining, remaining)
        lot.units_remaining = q_units(lot.units_remaining - take)
        remaining = q_units(remaining - take)
        consumed.append((lot, take))
    return consumed
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd services/api && uv run pytest tests/test_ledger.py -v`
Expected: `5 passed`.

- [ ] **Step 6: Commit**

```bash
git add services/api
git commit -m "feat(api): append-only ledger with FIFO lots and realised cost

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---
### Task 5: House funds seed and fund pricing

**Files:**
- Create: `services/api/app/seed/__init__.py`
- Create: `services/api/app/seed/funds.py`
- Create: `services/api/app/services/pricing.py`
- Create: `services/api/tests/test_pricing.py`

**Interfaces:**
- Consumes: `Fund`, `FundConstituent`, `Price` from Task 3.
- Produces:
  - `app.seed.funds.HOUSE_FUNDS: list[dict]` and `seed_funds(db) -> list[Fund]` (idempotent upsert by code).
  - `app.services.pricing.build_nav_series(prices: pd.DataFrame, weights: dict[str, float], base: float = 100.0) -> pd.Series` (daily-rebalanced weighted index, index = dates).
  - `publish_prices(db, fund_code: str, nav: pd.Series, units_in_issue: Decimal) -> int` (rows upserted, status `published`).
  - `latest_price(db, fund_code: str, as_of: date) -> Price | None` (most recent published price with `as_of <= date`).
  - `pricing_guard(db, as_of: date) -> list[str]` (fund codes without a published price on exactly `as_of`).

- [ ] **Step 1: Write the failing tests**

`services/api/tests/test_pricing.py`:

```python
from datetime import date
from decimal import Decimal

import pandas as pd
from sqlalchemy import select

from app.models import Fund, Price
from app.seed.funds import HOUSE_FUNDS, seed_funds
from app.services.pricing import build_nav_series, latest_price, pricing_guard, publish_prices


def test_seed_funds_creates_seven_funds_with_weights_summing_to_one(db):
    funds = seed_funds(db)
    db.commit()
    assert len(funds) == 7
    assert {f.code for f in funds} == {"ATR-CASH", "ATR-INC", "ATR-BAL", "ATR-GRW", "ATR-GLB", "ATR-DIV", "ATR-TEC"}
    for f in funds:
        assert sum(c.weight for c in f.constituents) == Decimal("1.0000")
    assert len(seed_funds(db)) == 7                       # idempotent
    assert len(db.scalars(select(Fund)).all()) == 7


def test_build_nav_series_is_daily_rebalanced_weighted_index():
    prices = pd.DataFrame(
        {"A": [100.0, 110.0, 121.0], "B": [100.0, 90.0, 81.0]},
        index=pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"]),
    )
    nav = build_nav_series(prices, {"A": 0.5, "B": 0.5})
    assert list(nav.round(6)) == [100.0, 100.0, 100.0]    # +10% and -10% at equal weight cancel
    nav2 = build_nav_series(prices, {"A": 1.0})
    assert list(nav2.round(6)) == [100.0, 110.0, 121.0]


def test_publish_latest_and_guard(db):
    seed_funds(db)
    nav = pd.Series([100.0, 101.5], index=pd.to_datetime(["2026-01-02", "2026-01-05"]))
    n = publish_prices(db, "ATR-BAL", nav, Decimal("1000000"))
    db.commit()
    assert n == 2
    p = latest_price(db, "ATR-BAL", date(2026, 1, 4))      # Sunday: falls back to Friday
    assert p is not None and p.as_of == date(2026, 1, 2) and p.nav == Decimal("100.000000")
    assert latest_price(db, "ATR-BAL", date(2026, 1, 1)) is None
    missing = pricing_guard(db, date(2026, 1, 5))
    assert "ATR-BAL" not in missing and len(missing) == 6
    assert publish_prices(db, "ATR-BAL", nav, Decimal("1000000")) == 2   # re-publish is an upsert
    assert len(db.scalars(select(Price).where(Price.fund_code == "ATR-BAL")).all()) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd services/api && uv run pytest tests/test_pricing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.seed'`.

- [ ] **Step 3: Write the house-fund seed**

`services/api/app/seed/__init__.py`:

```python
"""Seed data: house funds and synthetic people, accounts and transactions."""
```

`services/api/app/seed/funds.py`:

```python
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fund, FundConstituent

# (ticker, weight, asset_class, region, sector)
HOUSE_FUNDS: list[dict] = [
    dict(code="ATR-CASH", name="Atrium Cash Reserve", category="money_market", risk_band=1, fee_bps=10, min_investment="100",
         objective="Preserve capital and earn short-term Treasury yields with daily liquidity.",
         who_for="Emergency funds, parking cash between investments, horizons under one year.",
         constituents=[("SGOV", "0.6", "cash", "US", "treasury"), ("BIL", "0.4", "cash", "US", "treasury")]),
    dict(code="ATR-INC", name="Atrium Core Income", category="income", risk_band=2, fee_bps=25, min_investment="500",
         objective="Steady income from a diversified portfolio of US investment-grade bonds.",
         who_for="Income seekers and investors with horizons of one to three years.",
         constituents=[("BND", "0.5", "bond", "US", "aggregate"), ("AGG", "0.3", "bond", "US", "aggregate"), ("VCIT", "0.2", "bond", "US", "corporate")]),
    dict(code="ATR-BAL", name="Atrium Balanced", category="balanced", risk_band=3, fee_bps=35, min_investment="500",
         objective="Balanced growth and income through a 60/40 mix of US equities and bonds.",
         who_for="Medium horizons of three to seven years and moderate loss tolerance.",
         constituents=[("VTI", "0.6", "equity", "US", "broad"), ("BND", "0.4", "bond", "US", "aggregate")]),
    dict(code="ATR-GRW", name="Atrium Growth", category="growth", risk_band=4, fee_bps=40, min_investment="500",
         objective="Long-term capital growth from large-cap and growth-oriented US equities.",
         who_for="Long horizons over seven years and higher loss tolerance.",
         constituents=[("VOO", "0.5", "equity", "US", "broad"), ("QQQ", "0.3", "equity", "US", "technology"), ("VUG", "0.2", "equity", "US", "growth")]),
    dict(code="ATR-GLB", name="Atrium Global Equity", category="global_equity", risk_band=4, fee_bps=40, min_investment="500",
         objective="Diversified growth from developed and emerging markets outside and including the US.",
         who_for="Investors who want exposure beyond the US with long horizons.",
         constituents=[("VT", "0.5", "equity", "Global", "broad"), ("VXUS", "0.3", "equity", "DM_ex_US", "broad"), ("VEA", "0.2", "equity", "DM_ex_US", "broad")]),
    dict(code="ATR-DIV", name="Atrium Dividend", category="income_equity", risk_band=3, fee_bps=35, min_investment="500",
         objective="Growing income and moderate growth from quality US dividend payers.",
         who_for="Investors who want income with equity growth and medium to long horizons.",
         constituents=[("SCHD", "0.6", "equity", "US", "dividend"), ("VYM", "0.4", "equity", "US", "dividend")]),
    dict(code="ATR-TEC", name="Atrium Technology", category="sector", risk_band=5, fee_bps=50, min_investment="1000",
         objective="Concentrated growth from the US technology sector.",
         who_for="Thematic conviction as a small satellite allocation; high loss tolerance.",
         constituents=[("XLK", "0.6", "equity", "US", "technology"), ("VGT", "0.4", "equity", "US", "technology")]),
]

INCEPTION = date(2024, 10, 1)


def seed_funds(db: Session) -> list[Fund]:
    """Insert or update the seven house funds. Safe to run repeatedly."""
    out: list[Fund] = []
    for spec in HOUSE_FUNDS:
        fund = db.scalar(select(Fund).where(Fund.code == spec["code"]))
        if fund is None:
            fund = Fund(code=spec["code"], inception_on=INCEPTION)
            db.add(fund)
        fund.name = spec["name"]
        fund.category = spec["category"]
        fund.risk_band = spec["risk_band"]
        fund.fee_bps = spec["fee_bps"]
        fund.min_investment = Decimal(spec["min_investment"])
        fund.objective = spec["objective"]
        fund.who_for = spec["who_for"]
        fund.constituents = [
            FundConstituent(ticker=t, weight=Decimal(w), asset_class=a, region=r, sector=s)
            for (t, w, a, r, s) in spec["constituents"]
        ]
        out.append(fund)
    db.flush()
    return out


def all_tickers() -> list[str]:
    seen: list[str] = []
    for spec in HOUSE_FUNDS:
        for (t, *_rest) in spec["constituents"]:
            if t not in seen:
                seen.append(t)
    return seen
```

- [ ] **Step 4: Write the pricing service**

`services/api/app/services/pricing.py`:

```python
from datetime import date
from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fund, Price
from app.models.base import utcnow


def build_nav_series(prices: pd.DataFrame, weights: dict[str, float], base: float = 100.0) -> pd.Series:
    """NAV per unit of a fixed-weight, daily-rebalanced basket, starting at `base` on the first date.

    `prices` has one column per ticker (adjusted close) and a DatetimeIndex. Rows with any
    missing constituent are dropped so the series is only defined where every leg has a price.
    """
    cols = list(weights)
    px = prices[cols].dropna()
    if px.empty:
        raise ValueError("no overlapping price history for " + ", ".join(cols))
    w = pd.Series(weights, dtype="float64")
    daily = px.pct_change().fillna(0.0)
    basket = (daily * w).sum(axis=1)
    nav = (1.0 + basket).cumprod() * base
    nav.name = "nav"
    return nav


def publish_prices(db: Session, fund_code: str, nav: pd.Series, units_in_issue: Decimal) -> int:
    """Upsert published prices for every date in `nav`. Returns the number of rows written."""
    existing = {
        p.as_of: p for p in db.scalars(select(Price).where(Price.fund_code == fund_code)).all()
    }
    n = 0
    for ts, value in nav.items():
        as_of = ts.date() if hasattr(ts, "date") else ts
        row = existing.get(as_of)
        if row is None:
            row = Price(fund_code=fund_code, as_of=as_of)
            db.add(row)
        row.nav = Decimal(str(round(float(value), 6)))
        row.units_in_issue = Decimal(units_in_issue)
        row.status = "published"
        row.published_at = utcnow()
        n += 1
    db.flush()
    return n


def latest_price(db: Session, fund_code: str, as_of: date) -> Price | None:
    return db.scalar(
        select(Price)
        .where(Price.fund_code == fund_code, Price.status == "published", Price.as_of <= as_of)
        .order_by(Price.as_of.desc())
        .limit(1)
    )


def pricing_guard(db: Session, as_of: date) -> list[str]:
    """Fund codes with no published price on `as_of`. Non-empty means allocations must wait."""
    priced = set(
        db.scalars(select(Price.fund_code).where(Price.as_of == as_of, Price.status == "published")).all()
    )
    return [code for code in db.scalars(select(Fund.code).order_by(Fund.code)).all() if code not in priced]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd services/api && uv run pytest tests/test_pricing.py -v`
Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add services/api
git commit -m "feat(api): house fund seed and NAV pricing with guard

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Market data adapter (fake, yfinance, Alpaca)

**Files:**
- Create: `services/api/app/services/market_data.py`
- Create: `services/api/tests/test_market_data.py`

**Interfaces:**
- Consumes: `Settings` from Task 2.
- Produces (all in `app.services.market_data`):
  - `class MarketDataError(Exception)`.
  - `class MarketData(Protocol)` with `history(tickers: Sequence[str], start: date, end: date) -> pd.DataFrame` (DatetimeIndex of business days, one float column per ticker, adjusted close) and `latest_price(ticker: str) -> Decimal`.
  - `FakeMarketData(seed: int = 42)`: deterministic geometric random walk; rejects tickers that are not 1 to 6 upper-case letters.
  - `YFinanceMarketData(cache_dir: Path)`: `yfinance.download`, per-request CSV cache, raises `MarketDataError` on empty data.
  - `AlpacaMarketData(api_key, secret_key, history_provider: MarketData)`: latest trade from Alpaca, history delegated.
  - `get_market_data(settings: Settings) -> MarketData`.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/test_market_data.py`:

```python
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from app.config import Settings
from app.services.market_data import FakeMarketData, MarketDataError, YFinanceMarketData, get_market_data


def test_fake_history_is_business_days_and_deterministic():
    md = FakeMarketData(seed=7)
    df = md.history(["VTI", "BND"], date(2026, 1, 1), date(2026, 1, 31))
    assert list(df.columns) == ["VTI", "BND"]
    assert len(df) == 22                                  # business days in Jan 2026
    assert df.index[0] == pd.Timestamp("2026-01-01") and df.index[-1] == pd.Timestamp("2026-01-30")
    assert (df > 0).all().all()
    again = FakeMarketData(seed=7).history(["VTI", "BND"], date(2026, 1, 1), date(2026, 1, 31))
    pd.testing.assert_frame_equal(df, again)
    assert not df["VTI"].equals(df["BND"])                # different tickers, different paths


def test_fake_latest_price_matches_last_history_point():
    md = FakeMarketData(seed=7)
    last = md.history(["VOO"], date(2026, 1, 1), date(2026, 1, 31))["VOO"].iloc[-1]
    assert md.latest_price("VOO", as_of=date(2026, 1, 31)) == Decimal(str(round(float(last), 4)))


def test_fake_rejects_unknown_ticker_pattern():
    with pytest.raises(MarketDataError):
        FakeMarketData().history(["not a ticker"], date(2026, 1, 1), date(2026, 1, 10))


def test_yfinance_empty_frame_raises(tmp_path, monkeypatch):
    import app.services.market_data as mod

    monkeypatch.setattr(mod.yf, "download", lambda *a, **k: pd.DataFrame())
    with pytest.raises(MarketDataError):
        YFinanceMarketData(tmp_path).history(["ZZZZZZ"], date(2026, 1, 1), date(2026, 1, 10))


def test_get_market_data_honours_provider_setting():
    assert isinstance(get_market_data(Settings(_env_file=None, market_data_provider="fake")), FakeMarketData)
    assert isinstance(get_market_data(Settings(_env_file=None, market_data_provider="yfinance")), YFinanceMarketData)
    with pytest.raises(MarketDataError):
        get_market_data(Settings(_env_file=None, market_data_provider="bloomberg"))


@pytest.mark.network
@pytest.mark.skipif(os.environ.get("ATRIUM_NETWORK_TESTS") != "1", reason="set ATRIUM_NETWORK_TESTS=1 to hit yfinance")
def test_yfinance_real_download(tmp_path):
    df = YFinanceMarketData(Path(tmp_path)).history(["VTI", "BND"], date(2026, 9, 1), date(2026, 9, 30))
    assert {"VTI", "BND"} <= set(df.columns) and len(df) >= 18
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd services/api && uv run pytest tests/test_market_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.market_data'`.

- [ ] **Step 3: Write the adapter**

`services/api/app/services/market_data.py`:

```python
from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd
import yfinance as yf

from app.config import Settings

TICKER_RE = re.compile(r"^[A-Z]{1,6}$")


class MarketDataError(Exception):
    pass


class MarketData(Protocol):
    def history(self, tickers: Sequence[str], start: date, end: date) -> pd.DataFrame: ...
    def latest_price(self, ticker: str, as_of: date | None = None) -> Decimal: ...


def _validate(tickers: Sequence[str]) -> list[str]:
    bad = [t for t in tickers if not TICKER_RE.match(t)]
    if bad:
        raise MarketDataError(f"invalid ticker(s): {bad}")
    return list(tickers)


def _to_decimal(x: float) -> Decimal:
    return Decimal(str(round(float(x), 4)))


class FakeMarketData:
    """Deterministic geometric random walk per ticker. For tests and offline demos."""

    def __init__(self, seed: int = 42, start_price: float = 100.0, drift: float = 0.0003, vol: float = 0.01):
        self.seed, self.start_price, self.drift, self.vol = seed, start_price, drift, vol

    def _path(self, ticker: str, n: int) -> np.ndarray:
        h = int(hashlib.sha256(f"{self.seed}:{ticker}".encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(h)
        rets = rng.normal(self.drift, self.vol, size=n)
        rets[0] = 0.0
        return self.start_price * np.cumprod(1.0 + rets)

    def history(self, tickers: Sequence[str], start: date, end: date) -> pd.DataFrame:
        tickers = _validate(tickers)
        # Anchor every path at a fixed epoch so overlapping requests agree on prices.
        epoch = date(2020, 1, 1)
        idx = pd.bdate_range(epoch, end)
        frame = pd.DataFrame({t: self._path(t, len(idx)) for t in tickers}, index=idx)
        return frame.loc[pd.Timestamp(start):pd.Timestamp(end)]

    def latest_price(self, ticker: str, as_of: date | None = None) -> Decimal:
        as_of = as_of or date.today()
        df = self.history([ticker], as_of - timedelta(days=14), as_of)
        return _to_decimal(df[ticker].iloc[-1])


class YFinanceMarketData:
    """Adjusted closes from Yahoo Finance with a CSV cache keyed by (tickers, start, end)."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def history(self, tickers: Sequence[str], start: date, end: date) -> pd.DataFrame:
        tickers = _validate(tickers)
        key = hashlib.sha1(f"{','.join(sorted(tickers))}|{start}|{end}".encode()).hexdigest()[:16]
        cache = self.cache_dir / f"yf-{key}.csv"
        if cache.exists():
            return pd.read_csv(cache, index_col=0, parse_dates=True)
        raw = yf.download(tickers, start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
                          auto_adjust=True, progress=False, group_by="column", threads=False)
        if raw is None or raw.empty:
            raise MarketDataError(f"yfinance returned no data for {tickers} {start}..{end}")
        close = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw
        if isinstance(close, pd.Series):
            close = close.to_frame(name=tickers[0])
        close = close[tickers].astype("float64")
        close.index = pd.to_datetime(close.index).tz_localize(None)
        close.to_csv(cache)
        return close

    def latest_price(self, ticker: str, as_of: date | None = None) -> Decimal:
        _validate([ticker])
        if as_of is not None:
            df = self.history([ticker], as_of - timedelta(days=14), as_of)
            return _to_decimal(df[ticker].dropna().iloc[-1])
        info = yf.Ticker(ticker).fast_info
        price = getattr(info, "last_price", None) or info.get("lastPrice")
        if not price:
            raise MarketDataError(f"no last price for {ticker}")
        return _to_decimal(price)


class AlpacaMarketData:
    """Latest trade from Alpaca's data API; history delegated (Alpaca free data is IEX-only)."""

    def __init__(self, api_key: str, secret_key: str, history_provider: MarketData):
        from alpaca.data.historical import StockHistoricalDataClient

        self._client = StockHistoricalDataClient(api_key, secret_key)
        self._history = history_provider

    def history(self, tickers: Sequence[str], start: date, end: date) -> pd.DataFrame:
        return self._history.history(tickers, start, end)

    def latest_price(self, ticker: str, as_of: date | None = None) -> Decimal:
        _validate([ticker])
        if as_of is not None:
            return self._history.latest_price(ticker, as_of)
        from alpaca.data.requests import StockLatestTradeRequest

        trades = self._client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=ticker))
        trade = trades.get(ticker)
        if trade is None:
            raise MarketDataError(f"Alpaca has no latest trade for {ticker}")
        return _to_decimal(trade.price)


def get_market_data(settings: Settings) -> MarketData:
    provider = settings.market_data_provider.lower()
    if provider == "fake":
        return FakeMarketData(seed=settings.seed)
    if provider == "yfinance":
        return YFinanceMarketData(Path(settings.market_cache_dir))
    if provider == "alpaca":
        if not settings.alpaca_api_key or not settings.alpaca_secret_key:
            raise MarketDataError("ALPACA_API_KEY and ALPACA_SECRET_KEY are required for provider=alpaca")
        return AlpacaMarketData(settings.alpaca_api_key, settings.alpaca_secret_key,
                                YFinanceMarketData(Path(settings.market_cache_dir)))
    raise MarketDataError(f"unknown market data provider {provider!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd services/api && uv run pytest tests/test_market_data.py -v`
Expected: `5 passed, 1 skipped`.

- [ ] **Step 5: Run the network test once to prove the real provider works**

Run: `cd services/api && ATRIUM_NETWORK_TESTS=1 uv run pytest tests/test_market_data.py -k real_download -v`
Expected: `1 passed`. If Yahoo rate-limits, wait a minute and retry; do not change the code to pass.

- [ ] **Step 6: Commit**

```bash
git add services/api
git commit -m "feat(api): market data adapter with fake, yfinance and Alpaca providers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Portfolio valuation service and REST API

**Files:**
- Create: `services/api/app/services/portfolio.py`
- Create: `services/api/app/schemas/__init__.py`
- Create: `services/api/app/schemas/funds.py`
- Create: `services/api/app/schemas/portfolio.py`
- Create: `services/api/app/routers/funds.py`
- Create: `services/api/app/routers/accounts.py`
- Modify: `services/api/app/main.py` (include routers)
- Modify: `services/api/tests/conftest.py` (add `client` fixture)
- Create: `services/api/tests/test_portfolio_api.py`

**Interfaces:**
- Consumes: `holdings`, `q_cash` (Task 4); `latest_price` (Task 5); models (Task 3).
- Produces:
  - `app.services.portfolio.valuation(db, account_id: str, as_of: date) -> PortfolioView` with `PortfolioView(account_id, as_of, total_value, total_cost, pnl, pnl_pct, holdings: list[HoldingView], by_fund, by_asset_class, by_region: dict[str, Decimal])` and `HoldingView(instrument, name, units, price, price_as_of, value, cost_basis, pnl, pnl_pct)`.
  - `PriceUnavailable(Exception)` when a held fund has no published price on or before `as_of`.
  - Endpoints: `GET /funds`, `GET /funds/{code}`, `GET /funds/{code}/prices?start=&end=`, `GET /accounts/{account_id}/portfolio?as_of=`. 404s carry `{"detail": "..."}`.
  - Test fixture `client` (FastAPI `TestClient` bound to the test session).

- [ ] **Step 1: Add the `client` fixture**

Append to `services/api/tests/conftest.py`:

```python
@pytest.fixture()
def client(db):
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Write the failing tests**

`services/api/tests/test_portfolio_api.py`:

```python
from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from app.seed.funds import seed_funds
from app.services.ledger import apply_posting
from app.services.portfolio import PriceUnavailable, valuation
from app.services.pricing import publish_prices


@pytest.fixture()
def priced_funds(db):
    seed_funds(db)
    idx = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])
    publish_prices(db, "ATR-BAL", pd.Series([100.0, 102.0, 104.0], index=idx), Decimal("1000000"))
    publish_prices(db, "ATR-TEC", pd.Series([200.0, 190.0, 210.0], index=idx), Decimal("500000"))
    db.commit()


def buy(db, account, fund, units, price, day):
    apply_posting(db, account_id=account.id, instrument=fund, instrument_type="fund", posting_type="subscription",
                  units=Decimal(units), cash=-Decimal(units) * Decimal(price), price=Decimal(price), value_date=day, reference=f"SUB-{fund}")
    db.commit()


def test_valuation_totals_and_lookthrough(db, account, priced_funds):
    buy(db, account, "ATR-BAL", "100", "100", date(2026, 1, 2))
    buy(db, account, "ATR-TEC", "10", "200", date(2026, 1, 2))
    view = valuation(db, account.id, date(2026, 1, 6))
    assert view.total_value == Decimal("12500.00")                 # 100*104 + 10*210
    assert view.total_cost == Decimal("12000.00")
    assert view.pnl == Decimal("500.00")
    assert view.by_fund["ATR-BAL"] == Decimal("10400.00")
    assert view.by_asset_class["bond"] == Decimal("4160.00")      # 40% of ATR-BAL
    assert view.by_asset_class["equity"] == Decimal("8340.00")    # 6240 + 2100
    assert view.by_region["US"] == Decimal("12500.00")
    tec = next(h for h in view.holdings if h.instrument == "ATR-TEC")
    assert tec.pnl_pct == Decimal("5.00")


def test_valuation_uses_last_price_on_or_before_as_of(db, account, priced_funds):
    buy(db, account, "ATR-BAL", "10", "100", date(2026, 1, 2))
    view = valuation(db, account.id, date(2026, 1, 4))             # Sunday
    assert view.holdings[0].price_as_of == date(2026, 1, 2)
    assert view.total_value == Decimal("1000.00")


def test_valuation_raises_when_no_price_exists_yet(db, account, priced_funds):
    buy(db, account, "ATR-BAL", "10", "100", date(2026, 1, 2))
    with pytest.raises(PriceUnavailable):
        valuation(db, account.id, date(2026, 1, 1))


def test_portfolio_for_empty_account_is_zero(client, account, priced_funds):
    r = client.get(f"/accounts/{account.id}/portfolio?as_of=2026-01-06")
    assert r.status_code == 200
    body = r.json()
    assert body["total_value"] == "0.00" and body["holdings"] == [] and body["by_fund"] == {}


def test_portfolio_endpoint_returns_view(client, db, account, priced_funds):
    buy(db, account, "ATR-BAL", "100", "100", date(2026, 1, 2))
    r = client.get(f"/accounts/{account.id}/portfolio?as_of=2026-01-06")
    assert r.status_code == 200
    body = r.json()
    assert body["total_value"] == "10400.00"
    assert body["holdings"][0]["name"] == "Atrium Balanced"
    assert body["holdings"][0]["price_as_of"] == "2026-01-06"


def test_unknown_account_returns_404(client, priced_funds):
    r = client.get("/accounts/nope/portfolio")
    assert r.status_code == 404 and "account" in r.json()["detail"].lower()


def test_funds_endpoints(client, priced_funds):
    r = client.get("/funds")
    assert r.status_code == 200 and len(r.json()) == 7
    one = client.get("/funds/ATR-BAL").json()
    assert one["name"] == "Atrium Balanced" and len(one["constituents"]) == 2
    prices = client.get("/funds/ATR-BAL/prices?start=2026-01-05&end=2026-01-06").json()
    assert [p["as_of"] for p in prices] == ["2026-01-05", "2026-01-06"]


def test_unknown_fund_returns_404(client, priced_funds):
    assert client.get("/funds/NOPE").status_code == 404
    assert client.get("/funds/NOPE/prices").status_code == 404
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd services/api && uv run pytest tests/test_portfolio_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.portfolio'`.

- [ ] **Step 4: Write the portfolio service**

`services/api/app/services/portfolio.py`:

```python
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fund
from app.services.ledger import Holding, holdings, q_cash
from app.services.pricing import latest_price


class PriceUnavailable(Exception):
    pass


@dataclass(frozen=True)
class HoldingView:
    instrument: str
    name: str
    units: Decimal
    price: Decimal
    price_as_of: date
    value: Decimal
    cost_basis: Decimal
    pnl: Decimal
    pnl_pct: Decimal


@dataclass
class PortfolioView:
    account_id: str
    as_of: date
    total_value: Decimal = Decimal("0.00")
    total_cost: Decimal = Decimal("0.00")
    pnl: Decimal = Decimal("0.00")
    pnl_pct: Decimal = Decimal("0.00")
    holdings: list[HoldingView] = field(default_factory=list)
    by_fund: dict[str, Decimal] = field(default_factory=dict)
    by_asset_class: dict[str, Decimal] = field(default_factory=dict)
    by_region: dict[str, Decimal] = field(default_factory=dict)


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0.00")
    return q_cash(numerator / denominator * Decimal("100"))


def valuation(db: Session, account_id: str, as_of: date) -> PortfolioView:
    view = PortfolioView(account_id=account_id, as_of=as_of)
    by_class: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    by_region: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for h in holdings(db, account_id):
        fund = db.scalar(select(Fund).where(Fund.code == h.instrument))
        price = latest_price(db, h.instrument, as_of) if fund is not None else None
        if fund is None or price is None:
            raise PriceUnavailable(f"no published price for {h.instrument} on or before {as_of}")
        value = q_cash(h.units * price.nav)
        pnl = q_cash(value - h.cost_basis)
        view.holdings.append(HoldingView(
            instrument=h.instrument, name=fund.name, units=h.units, price=price.nav, price_as_of=price.as_of,
            value=value, cost_basis=h.cost_basis, pnl=pnl, pnl_pct=_pct(pnl, h.cost_basis),
        ))
        view.by_fund[h.instrument] = value
        for c in fund.constituents:
            slice_value = value * c.weight
            by_class[c.asset_class] += slice_value
            by_region[c.region] += slice_value
        view.total_value += value
        view.total_cost += h.cost_basis

    view.total_value = q_cash(view.total_value)
    view.total_cost = q_cash(view.total_cost)
    view.pnl = q_cash(view.total_value - view.total_cost)
    view.pnl_pct = _pct(view.pnl, view.total_cost)
    view.by_asset_class = {k: q_cash(v) for k, v in sorted(by_class.items())}
    view.by_region = {k: q_cash(v) for k, v in sorted(by_region.items())}
    return view
```

- [ ] **Step 5: Write the schemas**

`services/api/app/schemas/__init__.py`:

```python
"""Pydantic response models. Decimals serialise as strings so the web app never loses precision."""
```

`services/api/app/schemas/funds.py`:

```python
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ConstituentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ticker: str
    weight: Decimal
    asset_class: str
    region: str
    sector: str


class FundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str
    category: str
    risk_band: int
    fee_bps: int
    min_investment: Decimal
    objective: str
    who_for: str
    inception_on: date
    constituents: list[ConstituentOut]


class PriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    as_of: date
    nav: Decimal
    units_in_issue: Decimal
    status: str
```

`services/api/app/schemas/portfolio.py`:

```python
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class HoldingOut(BaseModel):
    instrument: str
    name: str
    units: Decimal
    price: Decimal
    price_as_of: date
    value: Decimal
    cost_basis: Decimal
    pnl: Decimal
    pnl_pct: Decimal


class PortfolioOut(BaseModel):
    account_id: str
    as_of: date
    total_value: Decimal
    total_cost: Decimal
    pnl: Decimal
    pnl_pct: Decimal
    holdings: list[HoldingOut]
    by_fund: dict[str, Decimal]
    by_asset_class: dict[str, Decimal]
    by_region: dict[str, Decimal]
```

- [ ] **Step 6: Write the routers and register them**

`services/api/app/routers/funds.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Fund, Price
from app.schemas.funds import FundOut, PriceOut

router = APIRouter(prefix="/funds", tags=["funds"])


def _fund_or_404(db: Session, code: str) -> Fund:
    fund = db.scalar(select(Fund).where(Fund.code == code))
    if fund is None:
        raise HTTPException(status_code=404, detail=f"fund {code} not found")
    return fund


@router.get("", response_model=list[FundOut])
def list_funds(db: Session = Depends(get_db)):
    return db.scalars(select(Fund).order_by(Fund.risk_band, Fund.code)).all()


@router.get("/{code}", response_model=FundOut)
def get_fund(code: str, db: Session = Depends(get_db)):
    return _fund_or_404(db, code)


@router.get("/{code}/prices", response_model=list[PriceOut])
def fund_prices(code: str, start: date | None = Query(None), end: date | None = Query(None), db: Session = Depends(get_db)):
    _fund_or_404(db, code)
    q = select(Price).where(Price.fund_code == code, Price.status == "published")
    if start:
        q = q.where(Price.as_of >= start)
    if end:
        q = q.where(Price.as_of <= end)
    return db.scalars(q.order_by(Price.as_of)).all()
```

`services/api/app/routers/accounts.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account
from app.schemas.portfolio import PortfolioOut
from app.services.portfolio import PriceUnavailable, valuation

router = APIRouter(prefix="/accounts", tags=["accounts"])


def account_or_404(db: Session, account_id: str) -> Account:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail=f"account {account_id} not found")
    return acc


@router.get("/{account_id}/portfolio", response_model=PortfolioOut)
def get_portfolio(account_id: str, as_of: date | None = Query(None), db: Session = Depends(get_db)):
    account_or_404(db, account_id)
    try:
        return valuation(db, account_id, as_of or date.today())
    except PriceUnavailable as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
```

In `services/api/app/main.py`, change the imports and registration:

```python
from app.routers import accounts, funds, health
...
    app.include_router(health.router)
    app.include_router(funds.router)
    app.include_router(accounts.router)
```

- [ ] **Step 7: Run all tests to verify they pass**

Run: `cd services/api && uv run pytest -v`
Expected: all pass (`26 passed, 1 skipped`).

- [ ] **Step 8: Commit**

```bash
git add services/api
git commit -m "feat(api): portfolio valuation with look-through and funds/accounts endpoints

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---
### Task 8: Synthetic data generator and auto-seed

**Files:**
- Create: `services/api/app/seed/generate.py`
- Modify: `services/api/app/main.py` (auto-seed in lifespan when `settings.auto_seed` and the DB is empty)
- Create: `services/api/tests/test_generate.py`

**Interfaces:**
- Consumes: `seed_funds`, `all_tickers`, `HOUSE_FUNDS` (Task 5); `build_nav_series`, `publish_prices` (Task 5); `apply_posting` (Task 4); `get_market_data` (Task 6); models (Task 3).
- Produces:
  - `app.seed.generate.PERSONAS: list[dict]` with the three named personas from spec §4.4 plus nine more synthetic investors.
  - `generate(db, settings, *, start: date = date(2024, 10, 1), end: date | None = None) -> GenerateReport` with `GenerateReport(people, accounts, instructions, postings, prices, last_price_date)`.
  - `is_seeded(db) -> bool`.
  - CLI: `uv run python -m app.seed.generate [--seed N] [--provider fake|yfinance] [--end YYYY-MM-DD]`.
  - Deterministic for a given `settings.seed`: running twice on fresh databases produces identical postings.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/test_generate.py`:

```python
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.config import Settings
from app.models import Account, Instruction, Person, Posting, Price
from app.seed.generate import PERSONAS, generate, is_seeded
from app.services.ledger import balance, holdings
from app.services.pricing import pricing_guard


def settings():
    return Settings(_env_file=None, market_data_provider="fake", seed=42)


def test_generate_populates_every_table_deterministically(db):
    assert is_seeded(db) is False
    report = generate(db, settings(), end=date(2026, 10, 9))
    db.commit()
    assert is_seeded(db) is True
    assert report.people == len(PERSONAS) == 12
    assert report.accounts == 9                                   # three staff personas have no account
    assert report.instructions == report.postings > 100
    assert db.scalar(select(Person).where(Person.email == "priya@atrium.demo")).kind == "investor"
    assert db.scalar(select(Person).where(Person.email == "daniel@atrium.demo")).kind == "advisor"
    assert db.scalar(select(Person).where(Person.email == "mei@atrium.demo")).kind == "ops"
    # every investor holds something and nothing is negative
    for acc in db.scalars(select(Account)).all():
        hs = holdings(db, acc.id)
        assert hs, f"{acc.number} has no holdings"
        for h in hs:
            assert balance(db, acc.id, h.instrument) >= 0
    # every instruction is settled and every posting references one
    assert all(i.state == "settled" for i in db.scalars(select(Instruction)).all())
    refs = {p.reference for p in db.scalars(select(Posting)).all()}
    assert all(i.id in refs for i in db.scalars(select(Instruction)).all())
    # prices exist for all seven funds on the last business day
    assert report.last_price_date == date(2026, 10, 9)
    assert pricing_guard(db, report.last_price_date) == []
    def fingerprint():
        return sorted((p.instrument, p.value_date, p.posting_type, p.units, p.cash) for p in db.scalars(select(Posting)).all())

    first = fingerprint()
    # determinism: a second run on a fresh schema yields identical postings (ids differ, facts do not)
    db.rollback()
    from app.db import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    generate(db, settings(), end=date(2026, 10, 9))
    db.commit()
    assert fingerprint() == first


def test_units_equal_net_amount_over_nav(db):
    generate(db, settings(), end=date(2026, 10, 9))
    db.commit()
    posting = db.scalar(select(Posting).where(Posting.posting_type == "subscription").limit(1))
    price = db.scalar(select(Price).where(Price.fund_code == posting.instrument, Price.as_of == posting.value_date))
    assert price is not None
    assert posting.units == (-posting.cash / price.nav).quantize(Decimal("0.000001"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd services/api && uv run pytest tests/test_generate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.seed.generate'`.

- [ ] **Step 3: Write the generator**

`services/api/app/seed/generate.py`:

```python
"""Deterministic synthetic world: 12 people, 9 investor accounts, two years of monthly investing.

Run:  uv run python -m app.seed.generate --seed 42 --provider fake
"""
from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Account, Fund, Instruction, Person, Posting
from app.seed.funds import HOUSE_FUNDS, all_tickers, seed_funds
from app.services.ledger import apply_posting, q_cash, q_units
from app.services.market_data import get_market_data
from app.services.pricing import build_nav_series, latest_price, publish_prices

# kind, full_name, email, country, risk_band, monthly_amount, preferred funds (weights)
PERSONAS: list[dict] = [
    dict(kind="investor", full_name="Priya Raman", email="priya@atrium.demo", country="US", risk_band=3,
         monthly="1500", funds={"ATR-BAL": 0.6, "ATR-GRW": 0.4}),
    dict(kind="advisor", full_name="Daniel Okafor", email="daniel@atrium.demo", country="US"),
    dict(kind="ops", full_name="Mei Tanaka", email="mei@atrium.demo", country="SG"),
    dict(kind="investor", full_name="Lucas Moreau", email="lucas@atrium.demo", country="US", risk_band=4,
         monthly="2500", funds={"ATR-GRW": 0.5, "ATR-TEC": 0.3, "ATR-GLB": 0.2}),
    dict(kind="investor", full_name="Aisha Khan", email="aisha@atrium.demo", country="US", risk_band=2,
         monthly="800", funds={"ATR-INC": 0.7, "ATR-CASH": 0.3}),
    dict(kind="investor", full_name="Tom Becker", email="tom@atrium.demo", country="US", risk_band=5,
         monthly="3000", funds={"ATR-TEC": 0.6, "ATR-GRW": 0.4}),
    dict(kind="investor", full_name="Sofia Rossi", email="sofia@atrium.demo", country="US", risk_band=3,
         monthly="1200", funds={"ATR-DIV": 0.5, "ATR-BAL": 0.5}),
    dict(kind="investor", full_name="Noah Williams", email="noah@atrium.demo", country="US", risk_band=1,
         monthly="500", funds={"ATR-CASH": 1.0}),
    dict(kind="investor", full_name="Hana Sato", email="hana@atrium.demo", country="JP", risk_band=4,
         monthly="2000", funds={"ATR-GLB": 0.6, "ATR-GRW": 0.4}),
    dict(kind="investor", full_name="Arjun Mehta", email="arjun@atrium.demo", country="US", risk_band=3,
         monthly="1000", funds={"ATR-BAL": 1.0}),
    dict(kind="investor", full_name="Grace Li", email="grace@atrium.demo", country="US", risk_band=2,
         monthly="700", funds={"ATR-INC": 0.5, "ATR-DIV": 0.5}),
    dict(kind="compliance", full_name="Omar Haddad", email="omar@atrium.demo", country="US"),
]


@dataclass
class GenerateReport:
    people: int
    accounts: int
    instructions: int
    postings: int
    prices: int
    last_price_date: date


def is_seeded(db: Session) -> bool:
    return (db.scalar(select(func.count()).select_from(Person)) or 0) > 0


def _month_starts(start: date, end: date) -> list[date]:
    out: list[date] = []
    d = date(start.year, start.month, 1)
    while d <= end:
        out.append(d)
        d = date(d.year + (d.month // 12), (d.month % 12) + 1, 1)
    return out


def _business_day_on_or_after(d: date, trading_days: set[date]) -> date | None:
    for i in range(0, 7):
        c = d + timedelta(days=i)
        if c in trading_days:
            return c
    return None


def generate(db: Session, settings: Settings, *, start: date = date(2024, 10, 1), end: date | None = None) -> GenerateReport:
    end = end or date.today()
    rng = random.Random(settings.seed)
    market = get_market_data(settings)

    # 1. Funds and prices from constituent history.
    funds = seed_funds(db)
    history = market.history(all_tickers(), start, end)
    prices_written = 0
    trading_days: set[date] = set()
    for spec in HOUSE_FUNDS:
        weights = {t: float(w) for (t, w, *_r) in spec["constituents"]}
        nav = build_nav_series(history, weights)
        prices_written += publish_prices(db, spec["code"], nav, Decimal("1000000"))
        trading_days |= {ts.date() for ts in nav.index}
    db.flush()
    last_price_date = max(trading_days)

    # 2. People and accounts.
    people: dict[str, Person] = {}
    accounts: list[tuple[Account, dict]] = []
    for i, spec in enumerate(PERSONAS, start=1):
        person = Person(kind=spec["kind"], full_name=spec["full_name"], email=spec["email"],
                        country=spec["country"], risk_band=spec.get("risk_band"))
        db.add(person)
        db.flush()
        people[spec["email"]] = person
        if spec["kind"] == "investor":
            acc = Account(person_id=person.id, number=f"ACC-{i:04d}", opened_on=start,
                          bank_last4=f"{rng.randint(1000, 9999)}", bank_verified=True)
            db.add(acc)
            db.flush()
            accounts.append((acc, spec))

    # 3. Monthly subscriptions, occasional redemptions.
    n_instr = n_post = 0
    for acc, spec in accounts:
        monthly = Decimal(spec["monthly"])
        for m in _month_starts(start, end):
            day = _business_day_on_or_after(m + timedelta(days=rng.randint(0, 5)), trading_days)
            if day is None or day > last_price_date:
                continue
            for code, w in spec["funds"].items():
                amount = q_cash(monthly * Decimal(str(w)))
                price = latest_price(db, code, day)
                if price is None:
                    continue
                units = q_units(amount / price.nav)
                instr = Instruction(account_id=acc.id, fund_code=code, type="subscribe", amount=amount, state="settled",
                                    dealing_date=day, requested_at=datetime(day.year, day.month, day.day, 9, tzinfo=timezone.utc),
                                    settled_at=datetime(day.year, day.month, day.day, 18, tzinfo=timezone.utc))
                db.add(instr)
                db.flush()
                apply_posting(db, account_id=acc.id, instrument=code, instrument_type="fund", posting_type="subscription",
                              units=units, cash=-amount, price=price.nav, value_date=day, reference=instr.id)
                n_instr += 1
                n_post += 1
            # one in eight months, redeem a quarter of the largest holding
            if rng.random() < 0.125:
                from app.services.ledger import holdings as _holdings

                hs = sorted(_holdings(db, acc.id), key=lambda h: h.units, reverse=True)
                if hs:
                    h = hs[0]
                    units_out = q_units(h.units * Decimal("0.25"))
                    price = latest_price(db, h.instrument, day)
                    if units_out > 0 and price is not None:
                        cash_in = q_cash(units_out * price.nav)
                        instr = Instruction(account_id=acc.id, fund_code=h.instrument, type="redeem", units=units_out,
                                            state="settled", dealing_date=day,
                                            requested_at=datetime(day.year, day.month, day.day, 10, tzinfo=timezone.utc),
                                            settled_at=datetime(day.year, day.month, day.day, 18, tzinfo=timezone.utc))
                        db.add(instr)
                        db.flush()
                        apply_posting(db, account_id=acc.id, instrument=h.instrument, instrument_type="fund",
                                      posting_type="redemption", units=-units_out, cash=cash_in, price=price.nav,
                                      value_date=day, reference=instr.id)
                        n_instr += 1
                        n_post += 1
    db.flush()
    return GenerateReport(people=len(people), accounts=len(accounts), instructions=n_instr,
                          postings=n_post, prices=prices_written, last_price_date=last_price_date)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Atrium synthetic data")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--provider", choices=["fake", "yfinance"], default=None)
    parser.add_argument("--end", type=date.fromisoformat, default=None)
    args = parser.parse_args()
    settings = get_settings()
    if args.seed is not None:
        settings = settings.model_copy(update={"seed": args.seed})
    if args.provider is not None:
        settings = settings.model_copy(update={"market_data_provider": args.provider})

    from app.db import SessionLocal, init_db

    init_db()
    with SessionLocal() as db:
        if is_seeded(db):
            print("database already seeded; nothing to do")
            return
        report = generate(db, settings, end=args.end)
        db.commit()
        print(report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Auto-seed on startup**

In `services/api/app/main.py` replace the lifespan:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings = get_settings()
    if settings.auto_seed:
        from app.db import SessionLocal
        from app.seed.generate import generate, is_seeded

        with SessionLocal() as db:
            if not is_seeded(db):
                generate(db, settings)
                db.commit()
    yield
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd services/api && uv run pytest tests/test_generate.py -v`
Expected: `2 passed` (takes a few seconds: ~2 years × 9 accounts).

- [ ] **Step 6: Generate a real local database with Yahoo prices and inspect it**

Run:

```bash
cd services/api && MARKET_DATA_PROVIDER=yfinance uv run python -m app.seed.generate --provider yfinance
```

Expected: prints `GenerateReport(people=12, accounts=9, instructions=..., postings=..., prices=..., last_price_date=2026-10-09)` (last trading day before today) and creates `services/api/atrium.db` and `services/api/data/cache/yf-*.csv`. Then:

```bash
cd services/api && uv run uvicorn app.main:app --port 8000
```

and open `http://localhost:8000/funds/ATR-BAL/prices?start=2026-10-01` in a browser. Expected: a JSON list of published prices with real-looking NAVs around 100–130.

- [ ] **Step 7: Commit**

```bash
git add services/api
git commit -m "feat(api): deterministic synthetic data generator and auto-seed

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Domain event bus with Pub/Sub adapter

**Files:**
- Create: `services/api/app/events.py`
- Modify: `services/api/app/services/pricing.py` (emit `PricePublished`)
- Modify: `services/api/app/main.py` (create the bus on the app state)
- Create: `services/api/tests/test_events.py`

**Interfaces:**
- Consumes: `Settings` (Task 2), `publish_prices` (Task 5).
- Produces (in `app.events`):
  - `Event(type: str, payload: dict, id: str, occurred_at: datetime)` dataclass; `to_json() -> str`.
  - `EventBus(Protocol)` with `publish(event: Event) -> None` and `subscribe(event_type: str, handler: Callable[[Event], None]) -> None`.
  - `InProcessEventBus` (synchronous handlers, keeps `history: list[Event]`).
  - `PubSubEventBus(project: str, topic: str, inner: InProcessEventBus)` publishes JSON with attribute `type` and also dispatches locally.
  - `get_event_bus(settings) -> EventBus`; `set_event_bus(bus)` / `current_bus()` module-level accessor used by services.
  - Event types used from now on: `PricePublished` `{fund_code, as_of, nav}`. Later plans add `LeadCreated`, `TrustScoreChanged`, `InstructionReceived`, `OrderPlaced`, `OrderFilled`, `TransactionPosted`, `StatementUploaded`, `MatchProposed`, `AlertRaised`, `CaseDecided` (spec §9).

- [ ] **Step 1: Write the failing tests**

`services/api/tests/test_events.py`:

```python
import json
from datetime import date
from decimal import Decimal

import pandas as pd

from app.config import Settings
from app.events import Event, InProcessEventBus, PubSubEventBus, current_bus, get_event_bus, set_event_bus
from app.seed.funds import seed_funds
from app.services.pricing import publish_prices


def test_in_process_bus_dispatches_to_subscribers_and_records_history():
    bus = InProcessEventBus()
    seen = []
    bus.subscribe("PricePublished", seen.append)
    bus.subscribe("Other", lambda e: (_ for _ in ()).throw(AssertionError("wrong handler")))
    ev = Event(type="PricePublished", payload={"fund_code": "ATR-BAL"})
    bus.publish(ev)
    assert seen == [ev] and bus.history == [ev]
    assert json.loads(ev.to_json())["payload"]["fund_code"] == "ATR-BAL"
    assert len(ev.id) == 32


def test_publish_prices_emits_one_event_per_date(db):
    bus = InProcessEventBus()
    set_event_bus(bus)
    seed_funds(db)
    nav = pd.Series([100.0, 101.0], index=pd.to_datetime(["2026-01-02", "2026-01-05"]))
    publish_prices(db, "ATR-BAL", nav, Decimal("1000000"))
    types = [e.type for e in bus.history]
    assert types == ["PricePublished", "PricePublished"]
    assert bus.history[1].payload == {"fund_code": "ATR-BAL", "as_of": "2026-01-05", "nav": "101.000000"}


def test_get_event_bus_returns_in_process_when_pubsub_disabled():
    bus = get_event_bus(Settings(_env_file=None, pubsub_enabled=False))
    assert isinstance(bus, InProcessEventBus)


def test_pubsub_bus_publishes_json_with_type_attribute(monkeypatch):
    sent = []

    class FakePublisher:
        def topic_path(self, project, topic):
            return f"projects/{project}/topics/{topic}"

        def publish(self, topic_path, data, **attrs):
            sent.append((topic_path, json.loads(data.decode()), attrs))

            class _F:
                def result(self, timeout=None):
                    return "msg-1"

            return _F()

    import app.events as mod

    monkeypatch.setattr(mod, "_make_publisher", lambda: FakePublisher())
    inner = InProcessEventBus()
    bus = PubSubEventBus(project="atrium-cup-2026", topic="atrium-events", inner=inner)
    bus.publish(Event(type="PricePublished", payload={"fund_code": "ATR-TEC"}))
    assert sent[0][0] == "projects/atrium-cup-2026/topics/atrium-events"
    assert sent[0][1]["type"] == "PricePublished" and sent[0][2] == {"type": "PricePublished"}
    assert len(inner.history) == 1
    assert current_bus() is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd services/api && uv run pytest tests/test_events.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.events'`.

- [ ] **Step 3: Write the event bus**

`services/api/app/events.py`:

```python
from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.config import Settings
from app.models.base import new_id, utcnow

Handler = Callable[["Event"], None]


@dataclass
class Event:
    type: str
    payload: dict
    id: str = field(default_factory=new_id)
    occurred_at: datetime = field(default_factory=utcnow)

    def to_json(self) -> str:
        return json.dumps(
            {"id": self.id, "type": self.type, "occurred_at": self.occurred_at.isoformat(), "payload": self.payload},
            default=str,
        )


class EventBus(Protocol):
    def publish(self, event: Event) -> None: ...
    def subscribe(self, event_type: str, handler: Handler) -> None: ...


class InProcessEventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self.history: list[Event] = []

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: Event) -> None:
        self.history.append(event)
        for handler in list(self._handlers.get(event.type, [])):
            handler(event)


def _make_publisher():
    from google.cloud import pubsub_v1

    return pubsub_v1.PublisherClient()


class PubSubEventBus:
    """Publishes every event to one Pub/Sub topic (attribute `type`) and dispatches locally too."""

    def __init__(self, project: str, topic: str, inner: InProcessEventBus | None = None) -> None:
        self._publisher = _make_publisher()
        self._topic_path = self._publisher.topic_path(project, topic)
        self._inner = inner or InProcessEventBus()

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._inner.subscribe(event_type, handler)

    def publish(self, event: Event) -> None:
        # Fire and forget: the client batches and retries; blocking here would stall seeding (thousands of events).
        self._publisher.publish(self._topic_path, event.to_json().encode("utf-8"), type=event.type)
        self._inner.publish(event)


_bus: EventBus | None = None


def set_event_bus(bus: EventBus) -> None:
    global _bus
    _bus = bus


def current_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = InProcessEventBus()
    return _bus


def get_event_bus(settings: Settings) -> EventBus:
    if settings.pubsub_enabled:
        if not settings.gcp_project:
            raise ValueError("GCP_PROJECT is required when PUBSUB_ENABLED=true")
        return PubSubEventBus(settings.gcp_project, settings.pubsub_topic)
    return InProcessEventBus()


def emit(event_type: str, payload: dict) -> Event:
    event = Event(type=event_type, payload=payload)
    current_bus().publish(event)
    return event
```

- [ ] **Step 4: Emit `PricePublished` from the pricing service**

In `services/api/app/services/pricing.py` add the import `from app.events import emit` and, inside the `for ts, value in nav.items()` loop of `publish_prices`, after `n += 1`:

```python
        emit("PricePublished", {"fund_code": fund_code, "as_of": as_of.isoformat(), "nav": f"{row.nav:.6f}"})
```

- [ ] **Step 5: Create the bus on startup and reset it between tests**

In `services/api/app/main.py`, at the top of `create_app()` after `settings = get_settings()`:

```python
    from app.events import get_event_bus, set_event_bus

    set_event_bus(get_event_bus(settings))
```

Append to `services/api/tests/conftest.py` so one test's subscribers never leak into the next:

```python
@pytest.fixture(autouse=True)
def _fresh_event_bus():
    from app.events import InProcessEventBus, set_event_bus

    set_event_bus(InProcessEventBus())
    yield
    set_event_bus(InProcessEventBus())
```

- [ ] **Step 6: Run all tests to verify they pass**

Run: `cd services/api && uv run pytest -v`
Expected: all pass (`32 passed, 1 skipped`).

- [ ] **Step 7: Commit**

```bash
git add services/api
git commit -m "feat(api): domain event bus with Pub/Sub adapter; emit PricePublished

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Authentication and role guards

**Files:**
- Create: `services/api/app/auth.py`
- Modify: `services/api/app/routers/accounts.py` (require an investor who owns the account, or staff)
- Create: `services/api/tests/test_auth.py`
- Modify: `services/api/tests/test_portfolio_api.py` (send the dev header)

**Interfaces:**
- Consumes: `Settings.auth_mode` (Task 2), `Person`/`Account` (Task 3), `account_or_404` (Task 7).
- Produces (in `app.auth`):
  - `CurrentUser(uid: str, email: str, roles: list[str], person_id: str | None)`.
  - `get_current_user(request, db) -> CurrentUser` FastAPI dependency. In `auth_mode="dev"` it reads header `X-Dev-User: <email>` and resolves roles from `Person.kind` (`investor` → `["investor"]`, staff kinds → `[kind, "staff"]`); missing or unknown email → 401. In `auth_mode="firebase"` it verifies `Authorization: Bearer <idToken>` with `firebase_admin.auth.verify_id_token`, then matches `Person.firebase_uid` or `Person.email`; failure → 401.
  - `require_roles(*roles) -> Depends` raising 403 unless the user has one of the roles.
  - `assert_account_access(user, account) -> None` raising 403 unless the user is staff or owns the account.
  - Web app (Task 11) sends `X-Dev-User` locally and the Firebase bearer token when deployed.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/test_auth.py`:

```python
import pytest

from app.auth import CurrentUser, get_current_user
from app.config import get_settings
from app.seed.generate import generate
from app.seed.funds import seed_funds


@pytest.fixture()
def world(db):
    seed_funds(db)
    from datetime import date

    generate(db, get_settings(), end=date(2026, 10, 9))
    db.commit()


def test_missing_dev_header_is_401(client, world):
    r = client.get("/accounts/anything/portfolio")
    assert r.status_code == 401


def test_malformed_dev_header_is_401_not_500(client, world):
    r = client.get("/accounts/anything/portfolio", headers={"X-Dev-User": "   "})
    assert r.status_code == 401
    r = client.get("/accounts/anything/portfolio", headers={"X-Dev-User": "nobody@nowhere.test"})
    assert r.status_code == 401


def test_investor_can_read_own_account_but_not_others(client, db, world):
    from sqlalchemy import select

    from app.models import Account, Person

    priya = db.scalar(select(Person).where(Person.email == "priya@atrium.demo"))
    lucas = db.scalar(select(Person).where(Person.email == "lucas@atrium.demo"))
    own = db.scalar(select(Account).where(Account.person_id == priya.id))
    other = db.scalar(select(Account).where(Account.person_id == lucas.id))
    assert client.get(f"/accounts/{own.id}/portfolio?as_of=2026-10-09", headers={"X-Dev-User": "priya@atrium.demo"}).status_code == 200
    assert client.get(f"/accounts/{other.id}/portfolio?as_of=2026-10-09", headers={"X-Dev-User": "priya@atrium.demo"}).status_code == 403


def test_staff_can_read_any_account(client, db, world):
    from sqlalchemy import select

    from app.models import Account

    acc = db.scalar(select(Account))
    for email in ("daniel@atrium.demo", "mei@atrium.demo", "omar@atrium.demo"):
        assert client.get(f"/accounts/{acc.id}/portfolio?as_of=2026-10-09", headers={"X-Dev-User": email}).status_code == 200


def test_firebase_mode_verifies_bearer_token(client, db, world, monkeypatch):
    import app.auth as auth_mod
    from sqlalchemy import select

    from app.models import Account, Person

    monkeypatch.setattr(get_settings(), "auth_mode", "firebase")
    monkeypatch.setattr(auth_mod, "_verify_firebase_token",
                        lambda token: {"uid": "fb-priya", "email": "priya@atrium.demo"} if token == "good" else (_ for _ in ()).throw(ValueError("bad")))
    priya = db.scalar(select(Person).where(Person.email == "priya@atrium.demo"))
    acc = db.scalar(select(Account).where(Account.person_id == priya.id))
    assert client.get(f"/accounts/{acc.id}/portfolio?as_of=2026-10-09", headers={"Authorization": "Bearer good"}).status_code == 200
    assert client.get(f"/accounts/{acc.id}/portfolio?as_of=2026-10-09", headers={"Authorization": "Bearer bad"}).status_code == 401
    assert client.get(f"/accounts/{acc.id}/portfolio?as_of=2026-10-09").status_code == 401
    monkeypatch.setattr(get_settings(), "auth_mode", "dev")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd services/api && uv run pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth'`.

- [ ] **Step 3: Write `auth.py`**

`services/api/app/auth.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Account, Person

STAFF_KINDS = {"advisor", "ops", "compliance", "admin"}


@dataclass(frozen=True)
class CurrentUser:
    uid: str
    email: str
    roles: list[str]
    person_id: str | None

    @property
    def is_staff(self) -> bool:
        return "staff" in self.roles


def _roles_for(person: Person) -> list[str]:
    return [person.kind, "staff"] if person.kind in STAFF_KINDS else [person.kind]


def _verify_firebase_token(token: str) -> dict:
    import firebase_admin
    from firebase_admin import auth as fb_auth

    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    return fb_auth.verify_id_token(token)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    settings = get_settings()
    if settings.auth_mode == "dev":
        email = (request.headers.get("X-Dev-User") or "").strip().lower()
        if not email:
            raise _unauthorized("X-Dev-User header required in dev auth mode")
        person = db.scalar(select(Person).where(Person.email == email))
        if person is None:
            raise _unauthorized(f"no person with email {email}")
        return CurrentUser(uid=f"dev:{email}", email=email, roles=_roles_for(person), person_id=person.id)

    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        raise _unauthorized("Bearer token required")
    try:
        claims = _verify_firebase_token(header.split(" ", 1)[1].strip())
    except Exception as e:  # firebase raises several exception types; all mean "not authenticated"
        raise _unauthorized("invalid or expired token") from e
    uid, email = claims.get("uid", ""), (claims.get("email") or "").lower()
    person = db.scalar(select(Person).where(Person.firebase_uid == uid))
    if person is None and email:
        person = db.scalar(select(Person).where(Person.email == email))
        if person is not None and not person.firebase_uid:
            person.firebase_uid = uid
            db.commit()
    if person is None:
        raise _unauthorized("authenticated user is not registered")
    return CurrentUser(uid=uid, email=email, roles=_roles_for(person), person_id=person.id)


def require_roles(*roles: str):
    def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not set(roles) & set(user.roles):
            raise HTTPException(status_code=403, detail=f"requires one of roles {sorted(roles)}")
        return user

    return _dep


def assert_account_access(user: CurrentUser, account: Account) -> None:
    if user.is_staff or account.person_id == user.person_id:
        return
    raise HTTPException(status_code=403, detail="not your account")
```

- [ ] **Step 4: Protect the portfolio endpoint**

In `services/api/app/routers/accounts.py` add `from app.auth import CurrentUser, assert_account_access, get_current_user` and change the handler signature and body:

```python
@router.get("/{account_id}/portfolio", response_model=PortfolioOut)
def get_portfolio(
    account_id: str,
    as_of: date | None = Query(None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    account = account_or_404(db, account_id)
    assert_account_access(user, account)
    try:
        return valuation(db, account_id, as_of or date.today())
    except PriceUnavailable as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
```

Note the order: 404 for an unknown account is returned to any authenticated user; 403 only when the account exists and is not theirs.

- [ ] **Step 5: Update the portfolio API tests to authenticate**

In `services/api/tests/test_portfolio_api.py`, add at the top:

```python
HDR = {"X-Dev-User": "priya@example.test"}
```

and pass `headers=HDR` to every `client.get(...)` on `/accounts/...` (three calls). The `account` fixture's person has that email. The `/funds` endpoints stay public.

- [ ] **Step 6: Run all tests to verify they pass**

Run: `cd services/api && uv run pytest -v`
Expected: all pass (`37 passed, 1 skipped`).

- [ ] **Step 7: Commit**

```bash
git add services/api
git commit -m "feat(api): dev and Firebase authentication with role guards on account data

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---
### Task 11: Web app scaffold, `/me` endpoint, CORS and the investor dashboard

**Files:**
- Create: `services/api/app/routers/me.py`; Modify: `services/api/app/main.py` (CORS middleware, `me` router); Modify: `services/api/app/config.py` (`cors_origins`); Create: `services/api/tests/test_me.py`
- Create (scaffolded): `apps/web/` via create-next-app
- Create: `apps/web/vitest.config.ts`
- Create: `apps/web/src/lib/allocation.ts`, `apps/web/src/lib/allocation.test.ts`
- Create: `apps/web/src/lib/config.ts`, `apps/web/src/app/api/config/route.ts`
- Create: `apps/web/src/lib/api.ts`, `apps/web/src/lib/firebase.ts`, `apps/web/src/lib/session.ts`
- Create: `apps/web/src/components/why-panel.tsx`, `apps/web/src/components/allocation-chart.tsx`, `apps/web/src/components/nav.tsx`
- Modify: `apps/web/src/app/layout.tsx`, `apps/web/src/app/page.tsx`
- Create: `apps/web/src/app/login/page.tsx`, `apps/web/src/app/investor/page.tsx`
- Modify: `apps/web/next.config.ts` (`output: "standalone"`)

**Interfaces:**
- Consumes: `get_current_user` (Task 10), `Account` (Task 3), `GET /accounts/{id}/portfolio` and `GET /funds` (Task 7).
- Produces:
  - `GET /me` → `{"uid","email","roles":[...],"person_id","accounts":[{"id","number"}]}` (401 without auth).
  - `Settings.cors_origins: str = "http://localhost:3000"` (comma-separated), applied with `CORSMiddleware`.
  - Web runtime config endpoint `GET /api/config` (Next route handler) → `{apiUrl, authMode, firebase:{apiKey,authDomain,projectId,appId}}` read from `process.env` at request time, so Cloud Run env vars work without a rebuild.
  - `toAllocationSeries(byX: Record<string,string>) -> {name, value, pct}[]` in `src/lib/allocation.ts`.
  - `<WhyPanel title evidence={[{label, detail}]} confidence model />` reusable component (spec P4).
  - Pages: `/login` (dev persona picker or Firebase email/password), `/investor` (dashboard: total value, P&L, holdings table, allocation donuts).

- [ ] **Step 1: Write the failing `/me` test**

`services/api/tests/test_me.py`:

```python
from datetime import date

import pytest

from app.config import get_settings
from app.seed.generate import generate


@pytest.fixture()
def world(db):
    generate(db, get_settings(), end=date(2026, 10, 9))
    db.commit()


def test_me_returns_roles_and_accounts(client, world):
    r = client.get("/me", headers={"X-Dev-User": "priya@atrium.demo"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "priya@atrium.demo" and body["roles"] == ["investor"]
    assert len(body["accounts"]) == 1 and body["accounts"][0]["number"] == "ACC-0001"
    staff = client.get("/me", headers={"X-Dev-User": "daniel@atrium.demo"}).json()
    assert staff["roles"] == ["advisor", "staff"] and staff["accounts"] == []


def test_me_requires_auth(client, world):
    assert client.get("/me").status_code == 401


def test_cors_allows_configured_origin(client, world):
    r = client.options("/funds", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd services/api && uv run pytest tests/test_me.py -v`
Expected: FAIL, `/me` returns 404 and the OPTIONS request lacks the CORS header.

- [ ] **Step 3: Add the `/me` router, CORS setting and middleware**

`services/api/app/routers/me.py`:

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.db import get_db
from app.models import Account

router = APIRouter(tags=["me"])


class AccountRef(BaseModel):
    id: str
    number: str


class MeOut(BaseModel):
    uid: str
    email: str
    roles: list[str]
    person_id: str | None
    accounts: list[AccountRef]


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MeOut:
    accounts = []
    if user.person_id:
        accounts = [AccountRef(id=a.id, number=a.number) for a in
                    db.scalars(select(Account).where(Account.person_id == user.person_id).order_by(Account.number)).all()]
    return MeOut(uid=user.uid, email=user.email, roles=user.roles, person_id=user.person_id, accounts=accounts)
```

In `services/api/app/config.py` add after `auth_mode`:

```python
    cors_origins: str = "http://localhost:3000"   # comma-separated list of allowed browser origins
```

In `services/api/app/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware
from app.routers import accounts, funds, health, me
...
    app = FastAPI(title="Atrium API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(funds.router)
    app.include_router(accounts.router)
    app.include_router(me.router)
```

- [ ] **Step 4: Run the API tests to verify they pass**

Run: `cd services/api && uv run pytest -v`
Expected: all pass (`40 passed, 1 skipped`).

- [ ] **Step 5: Commit the API half**

```bash
git add services/api
git commit -m "feat(api): /me endpoint and CORS for the web app

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [ ] **Step 6: Scaffold the Next.js app and add dependencies**

Run from the repo root:

```bash
pnpm create next-app@15 apps/web --ts --tailwind --eslint --app --src-dir --import-alias "@/*" --use-pnpm --turbopack
cd apps/web && pnpm add firebase@11 recharts@2 && pnpm add -D vitest@2
```

Expected: `apps/web` exists with `package.json`, `src/app/layout.tsx`, `src/app/page.tsx`; `pnpm dev` would start on port 3000.

Add to `apps/web/package.json` scripts: `"test": "vitest run"`. Set `apps/web/next.config.ts` to:

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
```

`apps/web/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { include: ["src/**/*.test.ts"], environment: "node" },
});
```

- [ ] **Step 7: Write the failing allocation test**

`apps/web/src/lib/allocation.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { toAllocationSeries, formatUsd } from "./allocation";

describe("toAllocationSeries", () => {
  it("turns an API map of decimal strings into sorted series with percentages", () => {
    const series = toAllocationSeries({ "ATR-BAL": "10400.00", "ATR-TEC": "2100.00" });
    expect(series).toEqual([
      { name: "ATR-BAL", value: 10400, pct: 83.2 },
      { name: "ATR-TEC", value: 2100, pct: 16.8 },
    ]);
  });
  it("returns an empty series for an empty map", () => {
    expect(toAllocationSeries({})).toEqual([]);
  });
});

describe("formatUsd", () => {
  it("formats decimal strings as US dollars", () => {
    expect(formatUsd("12500.5")).toBe("$12,500.50");
    expect(formatUsd("-3.2")).toBe("-$3.20");
  });
});
```

- [ ] **Step 8: Run the test to verify it fails**

Run: `cd apps/web && pnpm test`
Expected: FAIL with `Cannot find module './allocation'`.

- [ ] **Step 9: Write `allocation.ts`**

`apps/web/src/lib/allocation.ts`:

```ts
export type AllocationPoint = { name: string; value: number; pct: number };

export function toAllocationSeries(byKey: Record<string, string>): AllocationPoint[] {
  const entries = Object.entries(byKey).map(([name, v]) => ({ name, value: Number(v) }));
  const total = entries.reduce((s, e) => s + e.value, 0);
  return entries
    .sort((a, b) => b.value - a.value)
    .map((e) => ({ ...e, pct: total === 0 ? 0 : Math.round((e.value / total) * 1000) / 10 }));
}

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

export function formatUsd(value: string | number): string {
  return usd.format(Number(value));
}
```

- [ ] **Step 10: Run the test to verify it passes**

Run: `cd apps/web && pnpm test`
Expected: `3 passed`.

- [ ] **Step 11: Write runtime config, session and API client**

`apps/web/src/app/api/config/route.ts` (server side, read at request time):

```ts
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({
    apiUrl: process.env.API_URL ?? "http://localhost:8000",
    authMode: process.env.AUTH_MODE ?? "dev",
    firebase: {
      apiKey: process.env.FIREBASE_API_KEY ?? "",
      authDomain: process.env.FIREBASE_AUTH_DOMAIN ?? "",
      projectId: process.env.FIREBASE_PROJECT_ID ?? "",
      appId: process.env.FIREBASE_APP_ID ?? "",
    },
  });
}
```

`apps/web/src/lib/config.ts`:

```ts
export type RuntimeConfig = {
  apiUrl: string;
  authMode: "dev" | "firebase";
  firebase: { apiKey: string; authDomain: string; projectId: string; appId: string };
};

let cached: RuntimeConfig | null = null;

export async function getConfig(): Promise<RuntimeConfig> {
  if (cached) return cached;
  const res = await fetch("/api/config", { cache: "no-store" });
  cached = (await res.json()) as RuntimeConfig;
  return cached;
}
```

`apps/web/src/lib/firebase.ts`:

```ts
import { getApps, initializeApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";
import type { RuntimeConfig } from "./config";

export function firebaseAuth(cfg: RuntimeConfig): Auth {
  const app = getApps()[0] ?? initializeApp(cfg.firebase);
  return getAuth(app);
}
```

`apps/web/src/lib/session.ts` (who am I, in either auth mode):

```ts
import { getConfig } from "./config";
import { firebaseAuth } from "./firebase";

const DEV_KEY = "atrium.devUser";

export function setDevUser(email: string) {
  localStorage.setItem(DEV_KEY, email);
}

export function clearSession() {
  localStorage.removeItem(DEV_KEY);
}

export async function authHeaders(): Promise<Record<string, string>> {
  const cfg = await getConfig();
  if (cfg.authMode === "dev") {
    const email = localStorage.getItem(DEV_KEY);
    return email ? { "X-Dev-User": email } : {};
  }
  const user = firebaseAuth(cfg).currentUser;
  if (!user) return {};
  return { Authorization: `Bearer ${await user.getIdToken()}` };
}

export async function isSignedIn(): Promise<boolean> {
  const cfg = await getConfig();
  if (cfg.authMode === "dev") return !!localStorage.getItem(DEV_KEY);
  const auth = firebaseAuth(cfg);
  await auth.authStateReady();
  return !!auth.currentUser;
}
```

`apps/web/src/lib/api.ts`:

```ts
import { getConfig } from "./config";
import { authHeaders } from "./session";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const cfg = await getConfig();
  const res = await fetch(`${cfg.apiUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(await authHeaders()), ...(init.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export type Me = { uid: string; email: string; roles: string[]; person_id: string | null; accounts: { id: string; number: string }[] };
export type Holding = { instrument: string; name: string; units: string; price: string; price_as_of: string; value: string; cost_basis: string; pnl: string; pnl_pct: string };
export type Portfolio = {
  account_id: string; as_of: string; total_value: string; total_cost: string; pnl: string; pnl_pct: string;
  holdings: Holding[]; by_fund: Record<string, string>; by_asset_class: Record<string, string>; by_region: Record<string, string>;
};
```

- [ ] **Step 12: Write the shared components**

`apps/web/src/components/why-panel.tsx` (the explain-everything primitive; every AI feature in later plans renders through this):

```tsx
"use client";

import { useState } from "react";

export type Evidence = { label: string; detail: string };

export function WhyPanel({ title, evidence, confidence, model }: { title: string; evidence: Evidence[]; confidence?: number; model?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-slate-200 bg-white text-sm">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-3 py-2 text-left font-medium">
        <span>Why: {title}</span>
        <span className="text-xs text-slate-500">
          {confidence !== undefined && `confidence ${Math.round(confidence * 100)}%`} {open ? "▲" : "▼"}
        </span>
      </button>
      {open && (
        <div className="border-t border-slate-100 px-3 py-2">
          <ul className="list-disc space-y-1 pl-5">
            {evidence.map((e, i) => (
              <li key={i}><span className="font-medium">{e.label}:</span> {e.detail}</li>
            ))}
          </ul>
          {model && <p className="mt-2 text-xs text-slate-400">Generated by {model}. Illustrative, not advice.</p>}
        </div>
      )}
    </div>
  );
}
```

`apps/web/src/components/allocation-chart.tsx`:

```tsx
"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { formatUsd, type AllocationPoint } from "@/lib/allocation";

const COLORS = ["#0b5fff", "#5b8def", "#9fbcff", "#1f8a70", "#59b89c", "#f2a93b", "#d95d39"];

export function AllocationChart({ title, data }: { title: string; data: AllocationPoint[] }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <h3 className="mb-1 text-sm font-semibold">{title}</h3>
      {data.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-400">No holdings yet</p>
      ) : (
        <div className="h-52">
          <ResponsiveContainer>
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={2}>
                {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip formatter={(v: number, n: string, p) => [`${formatUsd(v)} (${p.payload.pct}%)`, n]} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
      <ul className="mt-1 grid grid-cols-2 gap-x-3 text-xs text-slate-600">
        {data.map((d, i) => (
          <li key={d.name} className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
            {d.name} {d.pct}%
          </li>
        ))}
      </ul>
    </div>
  );
}
```

`apps/web/src/components/nav.tsx`:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/investor", label: "Investor" },
  { href: "/advisor", label: "Advisor" },
  { href: "/operations", label: "Operations" },
  { href: "/compliance", label: "Compliance" },
];

export function Nav() {
  const path = usePathname();
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
        <Link href="/" className="text-lg font-bold tracking-tight text-[#0b5fff]">Atrium</Link>
        <nav className="flex gap-4 text-sm">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className={path.startsWith(l.href) ? "font-semibold text-slate-900" : "text-slate-500"}>
              {l.label}
            </Link>
          ))}
        </nav>
        <Link href="/login" className="ml-auto text-sm text-slate-500">Sign in</Link>
      </div>
    </header>
  );
}
```

- [ ] **Step 13: Write layout, home, login and investor pages**

`apps/web/src/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/nav";

export const metadata: Metadata = { title: "Atrium", description: "AI-native wealth operating system" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <Nav />
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 py-6 text-xs text-slate-400">
          Prototype with synthetic data and paper trading. Nothing here is investment advice.
        </footer>
      </body>
    </html>
  );
}
```

`apps/web/src/app/page.tsx`:

```tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/investor");
}
```

`apps/web/src/app/login/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { signInWithEmailAndPassword } from "firebase/auth";
import { getConfig, type RuntimeConfig } from "@/lib/config";
import { firebaseAuth } from "@/lib/firebase";
import { setDevUser } from "@/lib/session";

const PERSONAS = [
  { email: "priya@atrium.demo", label: "Priya Raman — investor" },
  { email: "lucas@atrium.demo", label: "Lucas Moreau — investor" },
  { email: "daniel@atrium.demo", label: "Daniel Okafor — advisor" },
  { email: "mei@atrium.demo", label: "Mei Tanaka — operations" },
  { email: "omar@atrium.demo", label: "Omar Haddad — compliance" },
];

export default function LoginPage() {
  const router = useRouter();
  const [cfg, setCfg] = useState<RuntimeConfig | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => { getConfig().then(setCfg); }, []);
  if (!cfg) return <p>Loading…</p>;

  if (cfg.authMode === "dev") {
    return (
      <div className="mx-auto max-w-md space-y-3">
        <h1 className="text-xl font-semibold">Choose a demo persona</h1>
        {PERSONAS.map((p) => (
          <button key={p.email} onClick={() => { setDevUser(p.email); router.push("/investor"); }}
                  className="block w-full rounded-lg border border-slate-200 bg-white px-4 py-3 text-left hover:border-[#0b5fff]">
            {p.label}
          </button>
        ))}
      </div>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await signInWithEmailAndPassword(firebaseAuth(cfg!), email, password);
      router.push("/investor");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-md space-y-3">
      <h1 className="text-xl font-semibold">Sign in</h1>
      <input className="w-full rounded border px-3 py-2" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input className="w-full rounded border px-3 py-2" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button className="rounded bg-[#0b5fff] px-4 py-2 text-white">Sign in</button>
    </form>
  );
}
```

`apps/web/src/app/investor/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, type Me, type Portfolio } from "@/lib/api";
import { formatUsd, toAllocationSeries } from "@/lib/allocation";
import { isSignedIn } from "@/lib/session";
import { AllocationChart } from "@/components/allocation-chart";
import { WhyPanel } from "@/components/why-panel";

export default function InvestorPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      if (!(await isSignedIn())) return router.push("/login");
      try {
        const m = await api<Me>("/me");
        setMe(m);
        if (m.accounts.length) setPortfolio(await api<Portfolio>(`/accounts/${m.accounts[0].id}/portfolio`));
      } catch (e) {
        setError(e instanceof ApiError ? `${e.status}: ${e.message}` : String(e));
      }
    })();
  }, [router]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!me) return <p>Loading…</p>;
  if (!me.accounts.length) return <p>{me.email} has no investment account. Staff workspaces arrive in later plans.</p>;
  if (!portfolio) return <p>Valuing portfolio…</p>;

  const pnlUp = Number(portfolio.pnl) >= 0;
  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold">Your portfolio</h1>
        <span className="text-sm text-slate-500">as of {portfolio.as_of} · {me.accounts[0].number}</span>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Stat label="Total value" value={formatUsd(portfolio.total_value)} />
        <Stat label="Invested" value={formatUsd(portfolio.total_cost)} />
        <Stat label="Gain / loss" value={`${formatUsd(portfolio.pnl)} (${portfolio.pnl_pct}%)`} tone={pnlUp ? "up" : "down"} />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <AllocationChart title="By fund" data={toAllocationSeries(portfolio.by_fund)} />
        <AllocationChart title="By asset class" data={toAllocationSeries(portfolio.by_asset_class)} />
        <AllocationChart title="By region" data={toAllocationSeries(portfolio.by_region)} />
      </div>
      <table className="w-full overflow-hidden rounded-lg border border-slate-200 bg-white text-sm">
        <thead className="bg-slate-100 text-left"><tr>
          <th className="px-3 py-2">Fund</th><th className="px-3 py-2 text-right">Units</th><th className="px-3 py-2 text-right">Price</th>
          <th className="px-3 py-2 text-right">Value</th><th className="px-3 py-2 text-right">Gain / loss</th>
        </tr></thead>
        <tbody>
          {portfolio.holdings.map((h) => (
            <tr key={h.instrument} className="border-t border-slate-100">
              <td className="px-3 py-2">{h.name} <span className="text-slate-400">{h.instrument}</span></td>
              <td className="px-3 py-2 text-right">{Number(h.units).toFixed(4)}</td>
              <td className="px-3 py-2 text-right">{formatUsd(h.price)} <span className="text-xs text-slate-400">{h.price_as_of}</span></td>
              <td className="px-3 py-2 text-right">{formatUsd(h.value)}</td>
              <td className={`px-3 py-2 text-right ${Number(h.pnl) >= 0 ? "text-emerald-700" : "text-red-600"}`}>{formatUsd(h.pnl)} ({h.pnl_pct}%)</td>
            </tr>
          ))}
        </tbody>
      </table>
      <WhyPanel
        title="how this valuation was computed"
        evidence={[
          { label: "Prices", detail: "Each fund is valued at its last published NAV on or before the as-of date." },
          { label: "Cost basis", detail: "Sum of remaining FIFO lots at their purchase price; realised gains are excluded." },
          { label: "Look-through", detail: "Asset class and region slices multiply each fund's value by its constituent weights." },
        ]}
        model="deterministic valuation engine (no model)"
      />
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" }) {
  const color = tone === "up" ? "text-emerald-700" : tone === "down" ? "text-red-600" : "text-slate-900";
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${color}`}>{value}</div>
    </div>
  );
}
```

- [ ] **Step 14: Build, run both services and check the dashboard by hand**

Run (terminal 1): `cd services/api && cp -n .env.example .env; uv run uvicorn app.main:app --port 8000`
Run (terminal 2): `cd apps/web && pnpm build && pnpm dev`

Open `http://localhost:3000`. Expected: redirect to `/login`, the persona picker appears; choose Priya; the dashboard shows a total value in the low tens of thousands of dollars, three donuts, a holdings table with ATR-BAL and ATR-GRW, and a collapsible Why panel. Choose Daniel: the page says he has no investment account. `pnpm build` must finish with no type errors.

- [ ] **Step 15: Commit**

```bash
git add apps/web
git commit -m "feat(web): Next.js app with login, investor dashboard and Why panel

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 12: Google Cloud project and Cloud Run deployment

**Files:**
- Create: `services/api/Dockerfile`, `services/api/.dockerignore`
- Create: `apps/web/Dockerfile`, `apps/web/.dockerignore`
- Create: `infra/preflight.sh`, `infra/setup_gcp.sh`, `infra/deploy.sh`

**Interfaces:**
- Consumes: the API (`PORT`, `DATABASE_URL`, `AUTO_SEED`, `CORS_ORIGINS`, `PUBSUB_ENABLED`, `GCP_PROJECT`) and web (`API_URL`, `AUTH_MODE`, `FIREBASE_*`) environment contracts from Tasks 2 and 11.
- Produces: project `atrium-cup-2026` in `us-central1` with Cloud SQL `atrium-db` (PostgreSQL 16, db-f1-micro), database `atrium`, secret `atrium-database-url`, service account `atrium-api@...`, Pub/Sub topic `atrium-events`, Cloud Run services `atrium-api` and `atrium-web` with public URLs. Later plans reuse `infra/deploy.sh` unchanged and add services beside it.

- [ ] **Step 1: Write the preflight script and run it**

`infra/preflight.sh`:

```bash
#!/usr/bin/env bash
# Checks everything deploy.sh needs. Exit 0 means go.
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-atrium-cup-2026}"
ok() { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; exit 1; }
command -v gcloud >/dev/null || fail "gcloud not installed"
gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . || fail "no active gcloud account (run: gcloud auth login)"
ok "gcloud authenticated as $(gcloud auth list --filter=status:ACTIVE --format='value(account)')"
gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1 && ok "project $PROJECT_ID exists" || printf '  warn project %s missing (setup_gcp.sh creates it)\n' "$PROJECT_ID"
[ -f services/api/Dockerfile ] && ok "api Dockerfile" || fail "services/api/Dockerfile missing"
[ -f apps/web/Dockerfile ] && ok "web Dockerfile" || fail "apps/web/Dockerfile missing"
[ -f services/api/uv.lock ] && ok "uv.lock present" || fail "run: cd services/api && uv lock"
[ -f apps/web/pnpm-lock.yaml ] && ok "pnpm-lock present" || fail "run: cd apps/web && pnpm install"
# Forbidden words live in an untracked file (one per line) so the public repo never spells them out.
if [ -f infra/.forbidden-words ]; then
  while IFS= read -r WORD; do
    [ -z "$WORD" ] && continue
    ! grep -rqi -- "$WORD" --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git --exclude=.forbidden-words . \
      && ok "forbidden word absent" || fail "a forbidden word from infra/.forbidden-words is in the tree"
  done < infra/.forbidden-words
else
  printf '  warn infra/.forbidden-words missing; create it (gitignored) with the name from the plan Global Constraints\n'
fi
echo "preflight passed"
```

Run: `bash infra/preflight.sh`
Expected: fails on the missing Dockerfiles (they come next); every other line `ok`.

- [ ] **Step 2: Write the API Dockerfile**

`services/api/.dockerignore`:

```
.venv
tests
*.db
*.db-journal
data/cache
.env
__pycache__
```

`services/api/Dockerfile`:

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
ENV PATH="/app/.venv/bin:$PATH" PORT=8080 PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
```

Verify locally only if Docker Desktop is running (it is installed but was stopped on the dev machine); otherwise Cloud Build verifies it in Step 6:

```bash
cd services/api && docker build -t atrium-api . && docker run --rm -p 8080:8080 -e AUTO_SEED=true atrium-api
```

Expected: `curl http://localhost:8080/health` → `{"status":"ok","service":"atrium-api","env":"local"}`.

- [ ] **Step 3: Write the web Dockerfile**

`apps/web/.dockerignore`:

```
node_modules
.next
.env*
```

`apps/web/Dockerfile`:

```dockerfile
FROM node:22-alpine AS build
RUN npm install -g pnpm@10
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production PORT=8080 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 8080
CMD ["node", "server.js"]
```

- [ ] **Step 4: Write the project setup script**

`infra/setup_gcp.sh` (idempotent; takes 5 to 10 minutes because Cloud SQL provisioning is slow):

```bash
#!/usr/bin/env bash
# One-time project setup. Usage: BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX bash infra/setup_gcp.sh
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-atrium-cup-2026}"
REGION="${REGION:-us-central1}"
BILLING="${BILLING_ACCOUNT:?set BILLING_ACCOUNT (gcloud billing accounts list)}"

gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1 || gcloud projects create "$PROJECT_ID" --name="Atrium AI Builder Cup 2026"
gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING" >/dev/null
gcloud config set project "$PROJECT_ID" >/dev/null

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  sqladmin.googleapis.com secretmanager.googleapis.com pubsub.googleapis.com aiplatform.googleapis.com \
  documentai.googleapis.com discoveryengine.googleapis.com bigquery.googleapis.com \
  firebase.googleapis.com identitytoolkit.googleapis.com iam.googleapis.com

if ! gcloud sql instances describe atrium-db >/dev/null 2>&1; then
  gcloud sql instances create atrium-db --database-version=POSTGRES_16 --edition=ENTERPRISE \
    --tier=db-f1-micro --region="$REGION" --storage-size=10GB --availability-type=ZONAL
fi
gcloud sql databases describe atrium --instance=atrium-db >/dev/null 2>&1 || gcloud sql databases create atrium --instance=atrium-db
DB_PASS="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)"
gcloud sql users create atrium --instance=atrium-db --password="$DB_PASS" >/dev/null 2>&1 \
  || gcloud sql users set-password atrium --instance=atrium-db --password="$DB_PASS"
CONN="$(gcloud sql instances describe atrium-db --format='value(connectionName)')"
DB_URL="postgresql+pg8000://atrium:${DB_PASS}@/atrium?unix_sock=/cloudsql/${CONN}/.s.PGSQL.5432"
gcloud secrets describe atrium-database-url >/dev/null 2>&1 || gcloud secrets create atrium-database-url --replication-policy=automatic
printf '%s' "$DB_URL" | gcloud secrets versions add atrium-database-url --data-file=- >/dev/null

SA="atrium-api@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || gcloud iam service-accounts create atrium-api --display-name="Atrium API"
for ROLE in roles/cloudsql.client roles/secretmanager.secretAccessor roles/pubsub.publisher roles/aiplatform.user \
            roles/documentai.apiUser roles/discoveryengine.viewer roles/bigquery.dataEditor roles/bigquery.jobUser roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" --role="$ROLE" --quiet >/dev/null
done
gcloud pubsub topics describe atrium-events >/dev/null 2>&1 || gcloud pubsub topics create atrium-events

firebase projects:addfirebase "$PROJECT_ID" >/dev/null 2>&1 || true
echo "setup complete for $PROJECT_ID"
echo "manual step (2 min): https://console.firebase.google.com/project/$PROJECT_ID/authentication/providers -> enable Email/Password"
```

Run: `BILLING_ACCOUNT=01DC00-40EA86-C3F761 bash infra/setup_gcp.sh`
Expected: ends with `setup complete for atrium-cup-2026`. If `projects create` says the id is taken, run again with `PROJECT_ID=atrium-cup-2026-<yourinitials>` and use that id everywhere below.

- [ ] **Step 5: Write the deploy script**

`infra/deploy.sh`:

```bash
#!/usr/bin/env bash
# Deploys both services. Usage: bash infra/deploy.sh   (AUTH_MODE=firebase to require Firebase sign-in)
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-atrium-cup-2026}"
REGION="${REGION:-us-central1}"
AUTH_MODE="${AUTH_MODE:-dev}"
bash "$(dirname "$0")/preflight.sh"
gcloud config set project "$PROJECT_ID" >/dev/null
CONN="$(gcloud sql instances describe atrium-db --format='value(connectionName)')"
SA="atrium-api@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud run deploy atrium-api --source services/api --region "$REGION" --allow-unauthenticated \
  --service-account "$SA" --add-cloudsql-instances "$CONN" \
  --set-secrets "DATABASE_URL=atrium-database-url:latest" \
  --set-env-vars "ENV=dev,AUTH_MODE=${AUTH_MODE},GCP_PROJECT=${PROJECT_ID},GCP_LOCATION=${REGION},MARKET_DATA_PROVIDER=yfinance,MARKET_CACHE_DIR=/tmp/cache,PUBSUB_ENABLED=true,AUTO_SEED=true" \
  --min-instances 1 --max-instances 3 --memory 1Gi --cpu 1 --timeout 300
API_URL="$(gcloud run services describe atrium-api --region "$REGION" --format='value(status.url)')"

gcloud run deploy atrium-web --source apps/web --region "$REGION" --allow-unauthenticated \
  --set-env-vars "API_URL=${API_URL},AUTH_MODE=${AUTH_MODE},FIREBASE_PROJECT_ID=${PROJECT_ID},FIREBASE_API_KEY=${FIREBASE_API_KEY:-},FIREBASE_AUTH_DOMAIN=${FIREBASE_AUTH_DOMAIN:-},FIREBASE_APP_ID=${FIREBASE_APP_ID:-}" \
  --min-instances 1 --max-instances 3 --memory 512Mi
WEB_URL="$(gcloud run services describe atrium-web --region "$REGION" --format='value(status.url)')"

gcloud run services update atrium-api --region "$REGION" --update-env-vars "CORS_ORIGINS=${WEB_URL},http://localhost:3000" >/dev/null
echo "API: $API_URL"
echo "WEB: $WEB_URL"
```

- [ ] **Step 6: Deploy and verify**

Run: `bash infra/deploy.sh`
Expected: two Cloud Build runs (3 to 6 minutes each the first time), then two URLs printed. Then:

```bash
curl -s "$(gcloud run services describe atrium-api --region us-central1 --format='value(status.url)')/health"
```

Expected: `{"status":"ok","service":"atrium-api","env":"dev"}`. The first request may take up to a minute while auto-seed downloads two years of prices and writes the ledger. Open the web URL in a browser: persona picker → Priya → dashboard with real data. Check logs if anything fails:

```bash
gcloud run services logs read atrium-api --region us-central1 --limit 100
```

- [ ] **Step 7: Commit**

```bash
git add services/api/Dockerfile services/api/.dockerignore apps/web/Dockerfile apps/web/.dockerignore infra
git commit -m "chore(infra): Dockerfiles, GCP setup and Cloud Run deploy scripts

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 13: Public repository, CI and README

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md` (run, test, deploy sections)

**Interfaces:**
- Consumes: test commands from Tasks 1 to 11, `infra/deploy.sh` from Task 12.
- Produces: public GitHub repository `XoAuraHiru/atrium` (submission requirement, spec §2.3) with CI running API tests and the web build on every push.

- [ ] **Step 1: Write the workflow**

`.github/workflows/ci.yml`:

```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:
jobs:
  api:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: services/api
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.12"
      - run: uv sync
      - run: uv run pytest
  web:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/web
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 10
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: pnpm
          cache-dependency-path: apps/web/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
      - run: pnpm test
      - run: pnpm build
```

- [ ] **Step 2: Extend the README**

Append to `README.md`:

````markdown
## Run locally

```bash
# API (http://localhost:8000, auto-seeds synthetic data on first start)
cd services/api && cp -n .env.example .env && uv sync && uv run uvicorn app.main:app --port 8000
# Web (http://localhost:3000) — in a second terminal
cd apps/web && pnpm install && pnpm dev
```

Sign in with a demo persona (dev auth mode). Tests: `cd services/api && uv run pytest`, `cd apps/web && pnpm test`.

## Deploy to Google Cloud

```bash
BILLING_ACCOUNT=<id> bash infra/setup_gcp.sh    # once
bash infra/deploy.sh                            # every time
```

Services: Cloud Run `atrium-api` and `atrium-web` in `us-central1`, Cloud SQL `atrium-db`, Pub/Sub topic `atrium-events`.

## Layout

| Path | What |
|---|---|
| `services/api` | FastAPI core: people, accounts, house funds, prices, append-only ledger, events, auth |
| `apps/web` | Next.js workspaces (investor today; advisor, operations, compliance in later plans) |
| `infra` | GCP setup, deploy and preflight scripts |
| `docs` | Blueprint, plans, diagrams |
````

- [ ] **Step 3: Create the public repository and push**

Run from the repo root:

```bash
bash infra/preflight.sh
gh repo create atrium --public --description "Atrium: AI-native wealth operating system (Google Cloud AI Builder Cup 2026, BFSI)" --source . --remote origin --push
```

Expected: `https://github.com/XoAuraHiru/atrium` exists with the full history; the `ci` workflow runs and both jobs pass (watch with `gh run watch`).

- [ ] **Step 4: Commit the workflow and README if not yet pushed**

```bash
git add .github README.md
git commit -m "chore: CI workflow and README run/deploy sections

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

## Done when

- `cd services/api && uv run pytest` passes (40 tests, 1 network test skipped).
- `cd apps/web && pnpm test && pnpm build` passes.
- The Cloud Run web URL shows Priya's dashboard with real Yahoo-priced house funds.
- `https://github.com/XoAuraHiru/atrium` is public with green CI.
- `bash infra/preflight.sh` reports every forbidden word absent (create `infra/.forbidden-words` locally with the name from Global Constraints; the file is gitignored).

Next plan: **Plan 2 — Acquire** (leads, Lead Score, Trust Score stage 1, Document AI, pipeline board, AI drafts), see `docs/superpowers/plans/README.md`.
