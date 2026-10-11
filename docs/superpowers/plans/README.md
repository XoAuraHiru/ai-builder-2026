# Atrium implementation plans

The blueprint (`docs/Atrium-Product-Blueprint.md`, v0.1, approved 11 Oct 2026) is too large for one plan. It is split into six plans that follow the build calendar in blueprint §10.2. Each plan produces working, deployable software on its own. Plans 2 to 6 are written just-in-time, after the previous plan has landed, so their tasks can name the real interfaces that exist by then.

| # | Plan | Blueprint scope | Calendar | Status |
|---|---|---|---|---|
| 1 | [Foundations](2026-10-11-atrium-foundations.md) | §9 data model, §5.3 house funds, B2 dashboard, P1 role shell, P2 auth, P7 synthetic data, §8.4 layout, Cloud Run deploy | Day 0–1 (Sat 11 – Sun 12 Oct) | Written, awaiting execution |
| 2 | Acquire | A1 lead capture, A2 enrichment, A3 Lead Score (BigQuery ML), A4 Trust Score stage 1, A5 Document AI identity, A7 pipeline board, A8 AI drafts with compliance check, A12 convert; first ADK agents (Lead Intelligence, Trust & Fraud) and the AI decision log (D11) | Day 2 (Mon 13 Oct) | Not started |
| 3 | Invest | B1 conversational risk profile, B3 Portfolio X-ray, B4 risk analytics, B6 What-if Studio (Monte Carlo + narrative), B7 fund explainers via Vertex AI Search over `data/funds/*.md`, B8 Investor Copilot agent, A10 personalised proposal, B11 instructions | Day 3 (Tue 14 Oct) | Not started |
| 4 | Trade | C1 watchlists and quotes, C2 order ticket to Alpaca paper, C3 Pre-trade Guardian agent, C4 order explainer; Trust Score stage 2 (B14) | Day 4 (Wed 15 Oct) | Not started |
| 5 | Operate | D1 blotter, D3 pricing approval with guard, D4 bank statement intelligence (Document AI), D5 Reconciliation agent, D6 four-eyes approvals with TOTP, D7 AML scenarios in BigQuery, D8 Compliance agent, D10 day-end job; ledger reversals | Day 5 (Thu 16 Oct) | Not started |
| 6 | Package | UX pass on all workspaces, seeded demo stories (three fraud cases), evaluation harness P6 if time, deck PDF, 3-minute video, submission checklist §11 | Day 6–7 (Fri 17 – Sat 18 Oct) | Not started |

Cut-lines when behind schedule are in blueprint §10.3. The never-cut set is: lead scoring with Why, Trust Score stage 1 with Document AI, What-if Studio, Pre-trade Guardian, agentic reconciliation, four-eyes approvals, AI decision log.

## Pinned external facts (verified 11 Oct 2026)

- Gemini model IDs on Vertex AI: `gemini-3.8-flash` (GA, 2 Sep 2026, 1M context, text/image/audio/video/PDF in) and `gemini-3.1-pro-preview` (preview, 19 Feb 2026). Both live in `Settings`.
- ADK: `pip install google-adk` version 2.11.0 (2 Oct 2026), Python ≥ 3.10, `from google.adk import Agent`; agents are `Agent(name=..., model=..., instruction=..., tools=[...])`. Plan 2 pins the `Runner` and session API from the ADK runtime docs before writing agent code.
- Local toolchain: Python 3.12.9, uv 0.11.16, Node 24.16, pnpm 10.33, gcloud SDK 527, gh 2.93 (authenticated as XoAuraHiru), Docker 27.5 (daemon not running by default), Chrome for PDF builds.
- GCP: billing account from `gcloud billing accounts list`; target project id `atrium-cup-2026` (created by Plan 1 Task 12).
