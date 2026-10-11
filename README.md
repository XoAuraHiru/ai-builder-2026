# Atrium — AI Builder Cup 2026 (BFSI track)

Team **Ctrl+Alt+Hiru**. Theme: *BFSI: Intelligent Risk, Fraud & Financial Experiences*.

Atrium is an AI-native wealth operating system for US and global markets:
**Acquire → Invest → Trade → Operate**, with Gemini, ADK agents, BigQuery and Document AI
doing the scoring, explaining, guarding and reconciling at every step.

## Documents

| File | What it is |
|---|---|
| `docs/Atrium-Product-Blueprint.md` | The design blueprint (what we build, features, AI design, architecture, 7-day plan, submission checklist) |
| `docs/Atrium-Product-Blueprint.pdf` | The same, as a printable PDF with bookmarks |
| `docs/diagrams/*.svg` | Pre-rendered diagrams used by the PDF and reusable in the deck |

## Rebuilding the PDF

Requires Python 3.12 with `markdown` and `pymupdf`, Node 18+ (for `npx`), and Google Chrome.

```bash
python tools/render_diagrams.py   # mermaid fences -> docs/diagrams/*.svg (only changed ones)
python tools/build_pdf.py         # markdown -> HTML -> PDF, then footer, bookmarks, TOC pages
```

## Run locally

```bash
# API on http://localhost:8000 (first start downloads ~2 years of ETF prices and seeds synthetic data)
cd services/api && cp -n .env.example .env && uv sync && uv run uvicorn app.main:app --port 8000
# Web on http://localhost:3000, in a second terminal
cd apps/web && pnpm install && pnpm dev
```

Open the web app and pick a demo persona (dev auth mode). Every person and transaction is synthetic.

Tests:

```bash
cd services/api && uv run pytest     # API: ledger, pricing, market data, portfolio, auth, events
cd apps/web && pnpm test             # web: pure data transforms
```

## Deploy to Google Cloud

```bash
BILLING_ACCOUNT=<id> bash infra/setup_gcp.sh    # once: project, APIs, Cloud SQL, secret, service account, Pub/Sub
bash infra/deploy.sh                            # every release: Cloud Run services atrium-api and atrium-web
```

Region `us-central1`. The scripts never change your active gcloud configuration. Test them without cloud access: `bash infra/tests/test_scripts.sh`.

The default deployment uses `AUTH_MODE=dev`: anyone with the URL can pick a demo persona, including staff. That is deliberate for a synthetic-data demo. `AUTH_MODE=firebase` requires Firebase sign-in with a verified email.

If Yahoo Finance is unreachable from Cloud Run, seeding falls back to the committed real-price snapshot in `services/api/app/seed/prices_snapshot.csv`. Refresh it locally with `uv run python -m app.seed.snapshot`.

## Layout

| Path | What |
|---|---|
| `services/api` | FastAPI core: people, accounts, house funds, prices, append-only ledger, events, auth |
| `apps/web` | Next.js workspaces: investor today; advisor, operations and compliance in later plans |
| `infra` | GCP setup, deploy and preflight scripts |
| `docs` | Blueprint, implementation plans, diagrams |

## Key dates (2026)

- 18 Oct — prototype submission deadline (deployed link, video < 3 min, public repo, PDF deck)
- 19 Oct – 6 Nov — evaluation; 7 Nov — finalists; 4 Dec — Grand Finale, Singapore
