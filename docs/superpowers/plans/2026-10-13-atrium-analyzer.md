# Atrium Return Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Anyone on the front door can ask "if I put this much into this fund or share for this long, what could it become?", see a simulation and (for a fund) the unit price history, and turn the answer into a fund order, a share order or an application.

**Architecture:**
- **Engine.** A thin `services/analyzer.py` over the existing What-if `simulate()`. A share is analysed as a one-constituent, fee-free "fund" over `market_monthly.csv` returns, so the simulation code is not forked. Shares also get SPY simulated on the same draws.
- **Record.** Every analysis is saved as an `Analysis` row. That row is the rate limit's counter, and the link carried by the lead, fund order, monthly plan or share order that follows.
- **Public API.** A new `routers/analyzer.py` with no sign-in, plus a signed-in-only explanation. `GET /funds/{code}/unit-history` serves the unit price chart.
- **Web.** An analyzer section on the front door. Pure logic lives in `lib/analyzer.ts`, unit-tested. The investor fund-orders page, the stock page and `/apply` read link parameters to pre-fill.

**Tech stack:** FastAPI, SQLAlchemy, pandas/numpy (existing engine), pytest; Next.js 15 client components, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-13-atrium-analyzer-design.md`.

## Global Constraints

- **Engines count; AI explains.** Every figure on screen comes from the engine. The explanation is Gemini Flash through the existing `write_narrative` with figure checking, for signed-in people only.
- **No change** to the Guardian, the fund-order checks, the monthly-plan checks or lead scoring. Pre-filled screens run exactly the checks they run today.
- **Look:** Atrium Daylight tokens and the kit from the experience plan. Charts reuse `FanChart`; the unit price chart is new but follows `GrowthChart`'s structure and scale helpers in `lib/scale.ts`.
- **Copy:** sentence case. Call the types "Unit trust (Atrium fund)" and "Shares". The disclosure text is fixed and lives in one place (`lib/analyzer.ts`, `DISCLOSURE`).
- **Accessibility:** real buttons and links; the step inputs are labelled; charts have a text summary; no horizontal page scroll at 390 px.
- **Data:** synthetic people only. Prices are the committed real prices.
- **Migrations:**
  - new columns go into `app/seed/migrate.py` `POSTGRES_MIGRATIONS`;
  - the new table comes from `create_all`.
- **Gates per task:**
  - API: `uv run pytest` in `services/api`.
  - Web: `pnpm tsc --noEmit`, `pnpm lint`, `pnpm vitest run` in `apps/web`.
- **Commits:** one per task, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Deploys:** report the cost on every deploy. This feature adds no AI cost for visitors; a signed-in explanation is about $0.002.

## Review Focus

1. **Input rules hold at the API**, not only in the form:
   - a share analysis with a monthly amount is refused;
   - a zero one-time amount is refused;
   - a unit-trust amount under the fund minimum is refused;
   - a unit-trust monthly amount under $50 is refused (Task 1 tests).
2. **SPY comparison uses the same drawn months** as the share, so the comparison is fair (Task 1 test with constructed returns).
3. **Rate limits** count per device or hashed IP and globally, before any simulation runs (Task 2 tests).
4. **An analysis link cannot be borrowed:**
   - an order, fund order, monthly plan or lead may only carry an analysis of the same kind and the same fund or symbol;
   - an analysis made by one signed-in person cannot be attached by another person;
   - an anonymous analysis can be attached by anyone, since the visitor had no identity yet (Tasks 4 and 5 tests).
5. **Unit price history:** the backtest joins the first published price without a jump, and points before launch are flagged (Task 3 tests).
6. **Phone width:** the analyzer steps stack, the charts scroll inside their own box, and the front door has no horizontal scroll (Task 9 screenshots at 390 px).

---

### Task 1: The analyzer engine

**Files:**
- Create: `services/api/app/services/analyzer.py`
- Create: `services/api/tests/test_analyzer.py`

**Interfaces:**
- Consumes: `simulate`, `Plan`, `WhatIfError` from `services/whatif.py`; `monthly_returns` from `services/fund_returns.py`; `load_market_monthly`, `instrument`, `STOCKS`, `ETFS` from `markets/universe.py`; `Fund`, `FundConstituent`.
- Produces:
  - `AnalysisRequest(kind: Literal["unit_trust", "share"], code: str, initial_usd: float, monthly_usd: float, years: int)`
  - `AnalyzerError(ValueError)`, whose message is shown to the person
  - `analyze(funds: dict[str, Fund], req: AnalysisRequest, *, paths=PATHS, fund_returns_df=None, share_returns_df=None) -> AnalysisResult`
  - `AnalysisResult`: `kind`, `code`, `name`, `fee_bps`, `min_investment`, the `WhatIfResult` for the investment (`result`), and `comparison: ScenarioResult | None` (SPY, shares only)
  - `share_options() -> list[dict]`: symbol, name, kind (`stock` or `etf`), first month with a price; only symbols with at least `MIN_SHARE_MONTHS` (120) of history

**Rules, checked before any simulation:**

| Rule | Message |
|---|---|
| `initial_usd > 0` | "Enter a one-time amount to invest." |
| unit trust: `initial_usd >= fund.min_investment` | "{fund name} needs at least {min} to start." |
| unit trust: `monthly_usd == 0 or monthly_usd >= 50` | "Monthly amounts start at $50." |
| share: `monthly_usd == 0` | "Monthly amounts are for unit trusts only." |
| share: the symbol is in `STOCKS` or `ETFS` and has at least 120 months of returns | "{symbol} has too little history to simulate." |
| `1 <= years <= 40` | "Choose 1 to 40 years." |

**How a share is simulated.** The share becomes a one-constituent fund named after the symbol, with `fee_bps=0` and `min_investment=0`. It is passed to `simulate()` with `returns=monthly_returns(load_market_monthly())` and the scenarios `[(name, {SYM: 1.0}), ("S&P 500 (SPY)", {"SPY": 1.0})]`. One `simulate()` call guarantees the same drawn months for both. `fund_return_frame` drops months either series lacks, so the window is the share's own; `history` reports it.

- [ ] **Step 1: Write the failing tests** in `tests/test_analyzer.py`, reusing the `returns_frame` and `fund` helpers pattern from `tests/test_whatif.py`:
  - `test_one_time_amount_is_required`
  - `test_unit_trust_minimum_is_enforced`
  - `test_unit_trust_monthly_below_50_is_refused` and `test_unit_trust_monthly_of_50_is_accepted`
  - `test_share_monthly_amount_is_refused`
  - `test_unknown_symbol_is_refused` and `test_short_share_history_is_refused` (119 months fails, 120 passes)
  - `test_share_is_fee_free_and_compared_with_spy`: constant returns AAA 1% and SPY 0.5% give exactly `1000*1.01**24` and `1000*1.005**24`
  - `test_share_and_spy_share_the_same_draws`: give AAA and SPY identical return series and assert identical percentiles
  - `test_unit_trust_matches_the_what_if_engine`: the same inputs through `simulate()` directly give the same `final`
  - `test_share_options_lists_only_symbols_with_ten_years`
- [ ] **Step 2: Run them and see them fail:** `uv run pytest tests/test_analyzer.py -q`
- [ ] **Step 3: Implement `services/analyzer.py`** as described. Keep `PATHS` from `whatif`. The share fund object is built in memory only, never added to a session.
- [ ] **Step 4: Run the whole suite:** `uv run pytest -q`
- [ ] **Step 5: Commit:** `feat(api): an analyzer engine for one fund or one share, with the S&P 500 beside shares`

---

### Task 2: Saved analyses, the public endpoint and its rate limit

**Files:**
- Create: `services/api/app/models/analysis.py` (export it from `models/__init__.py`)
- Create: `services/api/app/schemas/analyzer.py`
- Create: `services/api/app/routers/analyzer.py` (include it in `main.py`)
- Modify: `services/api/app/auth.py` (add `optional_user`)
- Modify: `services/api/app/config.py` (`analyzer_limit_per_hour: int = 30`, `analyzer_global_per_hour: int = 600`)
- Create: `services/api/tests/test_analyzer_api.py`

**Interfaces:**
- Consumes: Task 1; `ip_hash` from `services/capture_guard.py`; `write_narrative`, `WHATIF_TASK`, `whatif_facts`, `EXPLAIN_BUSY` from `routers/invest.py`.
- Produces:
  - **Table `analysis`:** `id`, `kind`, `code`, `initial_usd`, `monthly_usd`, `years`, `summary` (JSON: final percentiles, contributed, prob_loss, window), `person_id` (nullable FK person), `device_id`, `ip_hash`, `created_at`.
  - **`GET /analyzer/options`:** public. `{ "funds": [{code, name, risk_band, fee_bps, min_investment}], "shares": share_options() }`.
  - **`POST /analyzer`:** public. Body `{kind, code, initial_usd, monthly_usd, years, device_id}`. Returns `{id, kind, code, name, fee_bps, min_investment, result: WhatIfOut, comparison: ScenarioOut | null, disclosure_facts: {window_start, window_end, paths, fee_bps, selection_note: bool}}`. Status 201; 422 with the rule's message; 429 when limited.
  - **`POST /analyzer/{id}/explain`:** signed-in only (`get_current_user`). Returns `{narrative}` from `write_narrative(..., purpose="analyzer_narrative")`; 503 with `EXPLAIN_BUSY` if Gemini fails.
  - **`optional_user(request, db) -> CurrentUser | None`:** returns None when no `X-Dev-User` or `Authorization` header is present, and otherwise behaves as `get_current_user`, so a bad token is still a 401.

**Rate limit.** Before simulating, count `analysis` rows from the last hour where `device_id` or `ip_hash` matches (limit 30), and all rows (limit 600). Messages:
- per caller: "You've run many analyses in the last hour; please try again later."
- overall: "The analyzer is busy right now; please try again later."

The `analysis_out` helper turns an `AnalysisResult` into the response; the result's `WhatIfOut` is built the same way `run_what_if` builds it, so the web `WhatIf` type is reused.

- [ ] **Step 1: Write the failing tests:**
  - `test_visitor_can_analyse_without_signing_in` (no headers, 201, row saved with `person_id` None)
  - `test_signed_in_analysis_records_the_person`
  - `test_input_rules_return_422_with_the_message` (one case per rule)
  - `test_per_device_limit` and `test_global_limit` (set the limits low through settings overrides)
  - `test_options_list_funds_and_shares`
  - `test_explain_needs_sign_in` (401 without headers) and `test_explain_returns_a_checked_narrative` (fake LLM, as in `test_invest_api.py`)
  - `test_bad_token_is_still_401` for `optional_user`
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement** the model, schemas, router, `optional_user` and settings.
- [ ] **Step 4: Run the whole suite.**
- [ ] **Step 5: Commit:** `feat(api): anyone can run the analyzer; each run is saved and rate-limited`

---

### Task 3: Unit price history

**Files:**
- Modify: `services/api/app/routers/funds.py` (add `GET /funds/{code}/unit-history`)
- Modify: `services/api/app/schemas/funds.py` (`UnitPoint`, `UnitHistoryOut`)
- Modify: `services/api/tests/test_fund_api.py`

**Interfaces:**
- Consumes: `Price` (published rows), `fund_returns`, `constituent_weights`, `monthly_returns` from `services/fund_returns.py`.
- Produces: `GET /funds/{code}/unit-history`, public: `{ code, name, inception_on, points: [{date, price, backtest}] }`
  - From launch: every published daily price, with `backtest: false`.
  - Before launch: one point per month-start from the monthly backtest, with `backtest: true`. The series is chained backward from the first published price, so the month before launch ends on that price's level:

    `price_m = first_published / prod(1 + r) over the months from m+1 to launch`
  - If there are no published prices, the backtest is based at 100.

- [ ] **Step 1: Write the failing tests:**
  - `test_unit_history_flags_points_before_launch`
  - `test_backtest_joins_the_first_published_price` (the last backtest point times the launch month's return equals the first published price within a cent)
  - `test_unit_history_is_public`
  - `test_unknown_fund_is_404`
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the whole suite.**
- [ ] **Step 5: Commit:** `feat(api): a fund's unit price since 2007, backtest flagged before launch`

---

### Task 4: Leads carry the analysis

**Files:**
- Modify: `services/api/app/models/lead.py` (`analysis_id`, nullable FK `analysis.id`)
- Modify: `services/api/app/seed/migrate.py` (`ALTER TABLE lead ADD COLUMN IF NOT EXISTS analysis_id VARCHAR(32) REFERENCES analysis(id)`, the `IdMixin` id length)
- Modify: `services/api/app/schemas/leads.py` (`LeadIn.analysis_id: str | None`, and `LeadOut.analysis` with the analysis summary)
- Modify: `services/api/app/routers/leads.py` (validate on capture)
- Modify: `services/api/tests/test_leads_api.py`

**Rules:**
- The analysis must exist, be no older than 7 days, and not already be linked to a lead.
- A bad link is dropped silently and logged; the prospect's submission must never fail because of it.

- [ ] **Step 1: Write the failing tests:**
  - `test_lead_keeps_its_analysis`
  - `test_unknown_or_used_analysis_is_dropped_not_fatal`
  - `test_lead_out_shows_the_analysis_summary`
- [ ] **Step 2: Implement, run the suite.**
- [ ] **Step 3: Commit:** `feat(api): an application can carry the analysis that led to it`

---

### Task 5: Fund orders, monthly plans and share orders carry the analysis

**Files:**
- Modify: `services/api/app/models/instruction.py` (`Instruction.analysis_id`, `RecurringPlan.analysis_id`)
- Modify: `services/api/app/models/trading.py` (`TradeOrder.analysis_id`)
- Modify: `services/api/app/seed/migrate.py` (three `ADD COLUMN IF NOT EXISTS analysis_id`)
- Modify: `services/api/app/schemas/instructions.py` (`InstructionIn.analysis_id`, `RecurringIn.analysis_id`)
- Modify: `services/api/app/schemas/trading.py` (`OrderIn.analysis_id`)
- Create: `services/api/app/services/analysis_links.py` (`check_link(db, analysis_id, *, kind, code, person_id) -> str | None`)
- Modify: `services/api/app/routers/instructions.py` and `routers/trading.py` (call `check_link`; pass the id to the row)
- Create: `services/api/tests/test_analysis_links.py`

**Rules** in `check_link`. Unlike leads, an invalid link here is a 422, because the investor is signed in and the screen can say why:
- `kind` must match: `unit_trust` for fund orders and monthly plans, `share` for buy orders.
- `code` must match the fund code or the symbol.
- The analysis must be anonymous or made by the same person.
- A monthly plan may only carry a unit-trust analysis that had a monthly amount.

- [ ] **Step 1: Write the failing tests** (`kind` mismatch, `code` mismatch, another person's analysis, anonymous allowed, monthly plan without a monthly amount refused, happy paths for all three).
- [ ] **Step 2: Implement, run the suite.**
- [ ] **Step 3: Commit:** `feat(api): fund orders, monthly plans and share orders record the analysis they came from`

---

### Task 6: Web logic

**Files:**
- Create: `apps/web/src/lib/analyzer.ts`
- Create: `apps/web/src/lib/analyzer.test.ts`

**Produces:**
- Types `AnalyzerKind`, `AnalyzerOptions`, `Analysis` (reusing `WhatIf` and `ScenarioOut` from `lib/invest.ts`), `UnitHistory`.
- `validate(input, options): string | null`, mirroring the API rules with the same messages.
- `wholeShares(amountUsd: number, price: number): { shares: number; cost: number; left: number }`, rounding shares down.
- Link builders and readers:

  | Builder | Link |
  |---|---|
  | `fundOrderLink(a)` | `/investor/orders?analysis=..&fund=..&amount=..&monthly=..` |
  | `shareOrderLink(a, price)` | `/investor/markets/SYM?analysis=..&qty=..` |
  | `applyLink(a)` | `/apply?analysis=..&amount=..&monthly=..&years=..` |

  `readFundOrder`, `readShareOrder` and `readApply` parse those parameters defensively: bad numbers become null and never throw.
- `DISCLOSURE(kind, facts): string[]`, the fixed disclosure paragraphs from the spec.

- [ ] **Step 1: Write the failing tests:** each rule and its message; `wholeShares` (exact, leftover, an amount under one share); every link round-trips through its reader; junk parameters read as null; the disclosure includes the selection note only for shares.
- [ ] **Step 2: Implement, run the gates.**
- [ ] **Step 3: Commit:** `feat(web): analyzer rules, whole shares and pre-fill links`

---

### Task 7: The analyzer on the front door

**Files:**
- Create: `apps/web/src/components/analyzer.tsx`
- Create: `apps/web/src/components/unit-price-chart.tsx`
- Modify: `apps/web/src/app/page.tsx` (a section `id="analyze"` above `#journeys`, and a header link "Analyze")

**Behaviour:**
- **Steps:** type (two large choices), investment (fund cards with band and fee, or a searchable share list), amounts, years (slider 1 to 40 plus number input). A step is shown once the previous one has an answer. The monthly field appears only for unit trusts.
- **"Analyze":** posts to `/analyzer` with `deviceId()` and shows errors from the API as written.
- **Result, unit trust:**
  - the median and range headline, then `FanChart` with the one scenario;
  - money paid in and the chance of ending below it;
  - the unit price chart (Task 3 data; ranges 1Y, 2Y, Since 2007; backtest dashed);
  - the disclosure.
- **Result, shares:**
  - `FanChart` with the share and SPY as two scenarios;
  - the history window and the worst 12 months beside it;
  - the disclosure with the selection note.
- **Explanation:** shown only when `me` is set, as "Explain this" calling `/analyzer/{id}/explain`, rendered with `AiProse`. Visitors see no explanation button.
- **Next step** (Task 8 wires the destinations):
  - signed-in investor: "Invest in {fund}" or "Buy {n} shares";
  - everyone else: "Talk to an advisor about this plan".

- [ ] **Step 1: Build the components** with the kit (`Panel`, `Button`, `Notice`, `AiProse`).
- [ ] **Step 2: Run the gates; run the app** and analyse one fund and one share, signed out.
- [ ] **Step 3: Commit:** `feat(web): anyone can analyze a fund or a share from the front door`

---

### Task 8: From analysis to investment

**Files:**
- Modify: `apps/web/src/app/investor/orders/page.tsx`. Read `readFundOrder(searchParams)`, then:
  - pre-fill the subscribe form (fund, amount) and, if `monthly` is set, the monthly-plan form;
  - send `analysis_id` with both;
  - show a notice "Filled in from your analysis".
- Modify: `apps/web/src/app/investor/markets/[symbol]/page.tsx` and `components/order-ticket.tsx`:
  - the ticket gains `initialQuantity?: number` and `analysisId?: string`;
  - the page reads `readShareOrder` and passes both;
  - `analysis_id` is sent with the order.
- Modify: `apps/web/src/app/apply/page.tsx`. Read `readApply`, pre-fill "To invest now", "Every month" and "Years", and send `analysis_id`.
- Wrap each page's `useSearchParams` reader in a `Suspense` boundary, as the app router requires for client pages.
- Modify: `apps/web/src/app/advisor/leads/[id]/page.tsx`. When the lead has an analysis, show a panel "Their analysis" (type, investment, amounts, years, median and range).

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Run the gates. In the app:**
  - signed in as Priya, analyse Atrium Balanced with a monthly amount, then Invest: both forms are filled and the preview runs;
  - analyse NVDA, then Buy: the ticket shows the whole shares and the Guardian verdict;
  - signed out, analyse and then talk to an advisor: the form is filled; as Daniel, the lead shows the analysis.
- [ ] **Step 3: Commit:** `feat(web): an analysis becomes a fund order, a share order or an application`

---

### Task 9: Every page, looked at

- [ ] Screenshots of the front door analyzer (empty, unit-trust result, share result, an error) and the three pre-filled pages, at 1280 and 390 px. No horizontal page scroll at 390.
- [ ] Keyboard pass through the steps; the charts' text summaries are read.
- [ ] Fix what the screenshots show; commit `fix(web): analyzer visual pass`.

---

### Task 10: Release

- [ ] Run all gates.
- [ ] Update `README.md`: the analyzer in "What you can try", its cost line (no AI for visitors; $0.002 per signed-in explanation), and the new public endpoints.
- [ ] Update `docs/Atrium-Module-Flows.md` with a module for the analyzer and its conversions, and rebuild the PDF.
- [ ] Deploy (`bash infra/deploy.sh`). On the live site, check one analysis of each type signed out and signed in, and one conversion of each kind.
- [ ] Report the cost.
- [ ] Mark this plan done in `docs/superpowers/plans/README.md`.
