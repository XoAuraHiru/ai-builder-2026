# Atrium — AI Builder Cup 2026 (BFSI track)

Team **Ctrl+Alt+Hiru**. Theme: *BFSI: Intelligent Risk, Fraud & Financial Experiences*.

Atrium is an AI-native wealth operating system for US and global markets:
**Acquire → Invest → Trade → Operate**, with Gemini, ADK agents, BigQuery and Document AI
doing the scoring, explaining, guarding and reconciling at every step.

## Live demo

https://atrium-web-1070337126396.us-central1.run.app opens on Atrium's front door: what it is, the four stages, and eight people to choose from. Each person has a short guided story beside every page. Every person and number is synthetic.

## What you can try

| Persona | What to open |
|---|---|
| Priya Raman (investor) | Overview, What-if Studio (10,000 simulated futures over real history since 2007), Portfolio X-ray, Risk (the mix has drifted above the risk profile), fund pages with a cited reading, the risk-profile conversation, Fund orders, the Copilot agent, and Markets: checking 60 NVIDIA shares shows the Pre-trade Guardian holding the order for an advisor |
| Lucas Moreau (investor) | The X-ray (about a tenth of the portfolio is one company, through six ETFs), then buying more NVIDIA: the Guardian counts the shares held through his funds |
| Tom Becker (investor) | Selling all 120 Tesla shares from your browser: Atrium has never seen it, so the Guardian holds the sale as a possible account takeover |
| Hana Sato (investor) | Buying back PepsiCo, sold at a loss less than three weeks ago: the wash-sale warning |
| Daniel Okafor (advisor) | The lead pipeline with three fraud stories, identity checks, AI replies, proposals by Gemini Pro, and Held orders: a Gemini Pro review note, then release or reject |
| Mei Tanaka (operations) | Reconciliation: read the sample bank statement (a PDF read by Document AI), let the agent find matches for the typo, the missing reference and the split payment, and accept them; then the day-end, and ask for the draft prices to be published |
| Sam Ortiz (operations) | Approvals: Mei's requests, approved with the six-digit code from the demo authenticator; you cannot approve your own |
| Omar Haddad (compliance) | Alerts: structuring just under $10,000, money in and straight out, a payment from a stranger, and two accounts sharing one bank account; each with its evidence rows, a linked-entity graph and a Gemini Pro case review |

Every AI paragraph is set in a serif face beside a gold rule and says which model wrote it. Every dollar and percentage figure it writes is checked against the engine that produced it, and claims about funds cite the fact-sheet section they come from.

Trading uses paper money at real prices. By default, Atrium's own paper broker fills orders. Setting `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` (an Alpaca paper-trading account) sends them to Alpaca's paper API instead. The Pre-trade Guardian's verdict always comes from fixed rules; Gemini explains it and never changes it.

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
cd services/api && uv run pytest     # API: ledger, leads, trust, what-if, risk, X-ray, fund search, instructions, Guardian, orders, agents
cd apps/web && pnpm test             # web: formatting, chart scales, navigation, invest, order, market and trading helpers
```

## Deploy to Google Cloud

```bash
BILLING_ACCOUNT=<id> bash infra/setup_gcp.sh    # once: project, APIs, Cloud SQL, secret, service account, Pub/Sub
bash infra/deploy.sh                            # every release: Cloud Run services atrium-api and atrium-web
```

Region `us-central1`. The scripts never change your active gcloud configuration. Test them without cloud access: `bash infra/tests/test_scripts.sh`.

The day-end runs as the Cloud Run job `atrium-day-end` (the API image, `python -m app.ops.day_end`), started by Cloud Scheduler at 5:15 pm New York time on weekdays; operations can also start it from the workspace. The AML anomaly model is k-means trained in BigQuery ML (`uv run python -m app.ml.train_aml_model --bigquery`) and committed as `app/ml/aml_model.json`, so scoring needs no network. Bank account numbers are linked through an HMAC blind index whose key lives in Secret Manager.

The default deployment uses `AUTH_MODE=dev`: anyone with the URL can pick a demo persona, including staff. That is deliberate for a synthetic-data demo. `AUTH_MODE=firebase` requires Firebase sign-in with a verified email.

If Yahoo Finance is unreachable from Cloud Run, seeding falls back to the committed real-price snapshot in `services/api/app/seed/prices_snapshot.csv`. Refresh it locally with `uv run python -m app.seed.snapshot`.

The Invest features read committed data, so production never calls Yahoo for them: month-end prices since June 2007 (`app/seed/history_monthly.csv`) and ETF look-through profiles (`app/seed/etf_profiles.json`). Refresh both with `uv run python -m app.seed.history`, then rebuild the fund fact sheets with `uv run python -m app.knowledge.build` and rerun `infra/setup_gcp.sh` so Vertex AI Search re-indexes them.

The Trade features read committed market files too: thirty large US companies and seventeen ETFs, with their profiles (`app/seed/market_profiles.json`), daily closes since October 2024 (`app/seed/market_daily.csv`) and monthly closes since 2007 (`app/seed/market_monthly.csv`). Live quotes come from Yahoo Finance, cached for a minute. When Yahoo is unreachable, Atrium shows the last committed close and says so. Refresh the files with `uv run python -m app.markets.refresh`.

## Running cost

Both Cloud Run services scale to zero, so compute is billed only while requests are served and normally stays inside Cloud Run's free tier. The one always-on piece is Cloud SQL (db-f1-micro, 10 GB SSD, daily backups): about $9.40 a month. A budget alert emails the billing admins at 50, 90 and 100 percent of $15 a month.

AI is pay-per-use. Measured on the live system (Gemini 3.8 Flash on the global endpoint, October 2026 prices):

| Action | Cost each |
|---|---|
| Score a new lead (Gemini enrichment) | $0.0015 |
| Identity check (Gemini extraction + Document AI ID Proofing) | $0.102 |
| AI first-reply draft (ADK agent + compliance review) | $0.008 |
| Advisor question to the concierge agent | $0.003 |
| What-if, risk or X-ray explanation (Gemini, figures checked) | $0.002 |
| Fund "is it right for you?" reading (Gemini + one Vertex AI Search query) | $0.006 |
| Risk-profile conversation turn | $0.0007 |
| Investor Copilot question (ADK agent with tools) | $0.003, plus $0.004 per fund-document search |
| Order explanation before you confirm (Gemini Flash, figures checked) | $0.002 |
| Review note on a held order (Gemini Pro, figures checked) | $0.019, about 16 seconds |
| Personalised proposal (Gemini Pro + compliance review + searches), about 30 seconds | $0.045 |
| Read a bank statement PDF (Document AI Bank Statement Parser + Gemini Flash reading the narrations) | $0.75 Document AI list price per statement, plus $0.002 |
| Read a bank statement CSV (Gemini Flash reading the narrations) | $0.002 |
| Find matches (ADK reconciliation agent, Gemini Flash) | $0.004 to $0.014, about 10 to 20 seconds |
| AML case review (Gemini Pro, citations and figures checked) | $0.018 to $0.024, about 16 to 21 seconds |
| Day-end run with its morning brief (Cloud Run job + Gemini Flash) | $0.0008; the job's few seconds of compute and the one Cloud Scheduler job are inside the free tiers |

Vertex AI Search (the fund documents) is billed per query at the Enterprise list price of $4 per 1,000; its index is a few kilobytes, inside the free storage tier. At demo volumes (100 leads, 30 drafts, 30 questions and 20 identity checks, plus 150 Invest explanations and readings, 80 Copilot questions and 20 proposals a month, plus 100 order explanations and 10 held-order review notes) AI adds about $4.90, so the system ran at roughly $14.50 a month before the Operate release. Operate adds about $23.30 at demo volumes (30 statement PDFs, 30 reconciliations, 20 case reviews and 22 day-end runs a month), almost all of it Document AI's $0.75 per statement, for roughly $37.80 a month in all. Reading statements as CSV instead costs $0.002 each and brings the total back to about $15. Live quotes come from Yahoo Finance at no charge. Every call is listed with its cost under `GET /ai/usage` and on each lead's AI activity panel, and lands in BigQuery (`atrium.events`).

Cold start after idle time: about 6 seconds for the API and 2 to 4 seconds for the web app. For the judging window, keep both warm (about $23 a month extra):

```bash
API_MIN_INSTANCES=1 WEB_MIN_INSTANCES=1 bash infra/deploy.sh
```

## Layout

| Path | What |
|---|---|
| `services/api` | FastAPI core: ledger, leads, risk profiles, what-if engine, risk and X-ray analytics, fund documents and search, instructions, ADK agents |
| `apps/web` | Next.js workspaces on the Atrium design system: investor, advisor, operations and compliance |
| `infra` | GCP setup, deploy and preflight scripts |
| `docs` | Blueprint, implementation plans, diagrams |

## Key dates (2026)

- 18 Oct — prototype submission deadline (deployed link, video < 3 min, public repo, PDF deck)
- 19 Oct – 6 Nov — evaluation; 7 Nov — finalists; 4 Dec — Grand Finale, Singapore
