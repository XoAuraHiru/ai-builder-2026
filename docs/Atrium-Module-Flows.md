# Atrium — Module Flows

One flowchart per module, drawn from the code on `dev` (October 2026) and checked against the blueprint and the six implementation plans. Every step names **who** does it. Where the code differs from the blueprint, the module's notes say so.

## How to read the charts

Each box starts with its actor in bold. Colour shows the kind of actor:

| Colour | Actor kind | Actors |
|---|---|---|
| Blue | Person | Visitor, Prospect, Investor, Advisor (Daniel), Operations (Mei), Second approver (Sam), MLRO (Omar) |
| Grey | Web app | Next.js workspace in the browser |
| Green | Atrium engine | Core API, rule engines (Trust, Guardian, AML, reconciliation rules), ledger, day-end job |
| Amber | AI | Gemini Flash, Gemini Pro, ADK agents |
| Purple | Outside service | Document AI, Vertex AI Search, Firebase, broker (paper or Alpaca), Yahoo Finance, Cloud Scheduler |
| Red | Stop | The request is refused, with the reason shown |

A rule that runs everywhere: **AI explains and proposes; engines and rules count and decide; a person makes every fact-changing decision.** Every AI call is written to the AI decision log (module 14).

## Modules

| # | Pillar | Module | Main actors |
|---|---|---|---|
| 0 | Platform | Front door, sign-in and workspace | Visitor, Web, Firebase, Core API |
| 1 | Acquire | Lead capture and scoring | Prospect, Core API, Gemini Flash, Trust rules, Advisor |
| 2 | Acquire | Identity document check | Advisor, Gemini Flash, Document AI, Trust rules |
| 3 | Acquire | Working a lead: concierge, reply draft, proposal | Advisor, ADK agents, Gemini Pro, Vertex AI Search |
| 4 | Acquire | Convert to client | Advisor, Core API |
| 5 | Invest | Risk profile conversation | Investor, Gemini Flash, Risk-profile rules |
| 6 | Invest | Insights: What-if, X-ray, Risk, fund reading | Investor, analytics engines, Gemini Flash, Vertex AI Search |
| 7 | Invest | Fund orders (instructions) and monthly plans | Investor, Core API, day-end job |
| 8 | Invest | Investor Copilot | Investor, Investor Copilot agent |
| 9 | Trade | Placing an order through the Pre-trade Guardian | Investor, Guardian rules, Gemini Flash, broker |
| 10 | Trade | Held-order review | Advisor, Gemini Pro, Guardian rules, broker |
| 11 | Operate | Day-end run | Cloud Scheduler or Operations, day-end job, Gemini Flash |
| 12 | Operate | Bank statement intake and reconciliation | Operations, Document AI, Gemini Flash, reconciliation agent |
| 13 | Operate | Four-eyes approvals (prices, manual match, reversal) | Operations, second approver, Core API, ledger |
| 14 | Operate | AML monitoring and case decision | Day-end job, AML rules, k-means model, Gemini Pro, MLRO |
| 15 | Platform | AI decision log and event stream | Every AI call, Core API, Pub/Sub, BigQuery |

---

## 0. Front door, sign-in and workspace

Code: `apps/web/src/app/page.tsx`, `apps/web/src/lib/nav.ts`, `apps/web/src/lib/journeys.ts`, `services/api/app/auth.py`, `routers/me.py`.

```mermaid
flowchart TD
    A["<b>Visitor</b><br/>Opens the live link"]:::person --> B["<b>Web</b><br/>Shows the front door: what Atrium is,<br/>the four rooms, eight people to choose from"]:::web
    B --> C{"<b>Web</b><br/>Which sign-in mode?<br/>(/api/config)"}:::web
    C -- "dev (demo)" --> D["<b>Visitor</b><br/>Clicks Enter on a person"]:::person
    D --> E["<b>Web</b><br/>Keeps the person's email and sends<br/>X-Dev-User on every call"]:::web
    C -- "firebase" --> F["<b>Visitor</b><br/>Signs in with email on /login"]:::person
    F --> G["<b>Firebase Auth</b><br/>Verifies the email, issues an ID token"]:::ext
    G --> H["<b>Web</b><br/>Sends Authorization: Bearer token"]:::web
    E --> I["<b>Core API</b><br/>Maps the caller to a Person and roles<br/>(investor, advisor, ops, compliance, admin; staff)"]:::system
    H --> I
    I --> J{"<b>Core API</b><br/>Known person?"}:::system
    J -- no --> X["<b>Stop</b><br/>401, sign in again"]:::stop
    J -- yes --> K["<b>Web</b><br/>Opens that person's one workspace:<br/>top bar, own rail, journey guide"]:::web
    K --> L["<b>Visitor</b><br/>Follows the numbered journey steps"]:::person
    L --> M["<b>Web</b><br/>Marks a step done once its page is seen<br/>(browser storage, per person)"]:::web
    M --> L
    K -. "Switch person" .-> B

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

**Notes**
- Role to workspace: investor → Investor, advisor and admin → Advisor, ops → Operations, compliance → Compliance. Each person sees only their own workspace.
- `/apply` (the prospect form) and `/login` are public; everything else needs a person.
- The demo deploys with `AUTH_MODE=dev` on purpose: anyone with the link can pick any persona, staff included.
- **Docs vs code:** the blueprint lists an Admin workspace (P1). There is no separate one; admin is routed to the Advisor workspace and may also decide compliance alerts.

---

## 1. Lead capture and scoring

Code: `routers/leads.py` (`POST /leads`, `POST /leads/score-pending`), `services/lead_pipeline.py`, `services/enrichment.py`, `ml/lead_model.py`, `services/trust.py`, `services/capture_guard.py`.

```mermaid
flowchart TD
    A["<b>Prospect</b><br/>Fills in the form on /apply:<br/>goals, horizon, amount, source of funds"]:::person --> B["<b>Web</b><br/>Posts the lead with a device id"]:::web
    B --> C{"<b>Core API</b><br/>Capture guard: too many leads from<br/>this device, IP, or overall this hour?"}:::system
    C -- yes --> X["<b>Stop</b><br/>429, try again later"]:::stop
    C -- no --> D["<b>Core API</b><br/>Saves the lead, emits LeadCreated"]:::system
    D --> E["<b>Gemini Flash</b><br/>Enrichment: structured facts from the<br/>free text, risk appetite, next best action"]:::ai
    E --> F{"<b>Core API</b><br/>Did Gemini answer?"}:::system
    F -- no --> G["<b>Core API</b><br/>Records why the AI part is missing;<br/>deterministic scores still run"]:::system
    F -- yes --> H["<b>Lead model</b><br/>Lead Score 0-100 with factors for and against<br/>(logistic regression, BigQuery ML coefficients)"]:::system
    G --> H
    H --> I["<b>Trust rules, stage 1</b><br/>Disposable email, phone, duplicates, device velocity,<br/>inconsistent answers → score and band"]:::system
    I --> J["<b>Core API</b><br/>Emits LeadScored and TrustScoreChanged"]:::system
    J --> K["<b>Web</b><br/>Thanks the prospect<br/>(the submission never fails because scoring did)"]:::web
    J --> L["<b>Advisor</b><br/>Opens Leads: 'look at these first',<br/>then 'worth a call'"]:::person
    L -. "leads still pending" .-> M["<b>Advisor</b><br/>Asks to score pending leads<br/>(10 per request)"]:::person
    M --> E

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

**Trust bands:** 80 and above `clear`; 50 to 79 `review`; below 50 `high_risk`; a blocking signal makes it `blocked`. A rising score adds friction; only a person blocks or converts.

**Docs vs code**
- Blueprint §8.3 shows scoring as asynchronous agents fed by Pub/Sub. The code scores **inline** in the capture request, with `score-pending` as the catch-up path. Pub/Sub only carries the events outward.
- Blueprint A3/A4 name BigQuery ML for both the Lead Score and lead anomaly detection. The Lead Score uses committed model coefficients (`lead_model.json`); stage-1 Trust is fixed rule weights plus Gemini's enrichment, with no anomaly model at the lead stage.
- A6 sanctions and PEP screening is not built (P1 in the blueprint).

---

## 2. Identity document check

Code: `POST /leads/{id}/documents`, `services/identity.py`, `services/trust.py`.

```mermaid
flowchart TD
    A["<b>Advisor</b><br/>Uploads the prospect's passport or<br/>driving licence on the lead page"]:::person --> B{"<b>Core API</b><br/>Image or PDF, under the size limit?"}:::system
    B -- no --> X["<b>Stop</b><br/>415 or 413 with the reason"]:::stop
    B -- yes --> C["<b>Gemini Flash</b><br/>Reads the fields: name, date of birth,<br/>document number, expiry"]:::ai
    B -- yes --> D["<b>Document AI ID Proofing</b><br/>Fraud signals: tampering, screen photo,<br/>image manipulation (when configured)"]:::ext
    C --> E["<b>Core API</b><br/>Compares the document with the form:<br/>name match, date of birth, still valid"]:::system
    D --> E
    E --> F["<b>Core API</b><br/>Writes findings, some blocking;<br/>logs the AI decision; the image is not stored"]:::system
    F --> G["<b>Trust rules</b><br/>Recompute the Trust Score with the<br/>identity findings"]:::system
    G --> H["<b>Advisor</b><br/>Reads the extracted fields, findings,<br/>new score and band; decides what next"]:::person
    C -. "Gemini unavailable" .-> Y["<b>Stop</b><br/>502, document analysis unavailable"]:::stop

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

**Docs vs code:** the blueprint sequence has the **prospect** uploading the ID with the form. In the code the upload is a **staff-only** step on the lead page; the public form takes no documents.

---

## 3. Working a lead: concierge, reply draft, proposal

Code: `POST /leads/{id}/ask`, `/draft-reply`, `/proposal`, `PATCH /leads/{id}/stage`; `agents/advisor.py`, `services/compliance.py`, `services/proposal.py`.

```mermaid
flowchart TD
    A["<b>Advisor</b><br/>Opens a lead: scores, signals, factors,<br/>AI activity and cost"]:::person --> B{"<b>Advisor</b><br/>What do I need?"}:::person

    B -- "a question" --> C["<b>Concierge router agent</b><br/>Routes to Lead Intelligence or Trust & Fraud"]:::ai
    C --> D["<b>Specialist ADK agent</b><br/>Reads the lead snapshot with tools;<br/>prospect text is treated as data"]:::ai
    D --> E["<b>Advisor</b><br/>Reads the answer"]:::person

    B -- "a first reply" --> F["<b>Lead Intelligence agent</b><br/>Drafts the email in the firm's tone"]:::ai
    F --> G["<b>Compliance check tool</b><br/>Phrase rules + Gemini: guarantees, promises,<br/>unbalanced performance, urgency, missing risk"]:::ai
    G -- "findings" --> F
    G -- "ok" --> H["<b>Core API</b><br/>Final compliance check, logs the decision"]:::system
    H --> I["<b>Advisor</b><br/>Reviews the draft and sends it themselves"]:::person

    B -- "a proposal" --> J{"<b>Core API</b><br/>Trust band high_risk or blocked?"}:::system
    J -- yes --> X["<b>Stop</b><br/>409, resolve the trust review first"]:::stop
    J -- no --> K["<b>Core API</b><br/>Provisional band, recommended fund mix,<br/>Monte Carlo projection"]:::system
    K --> L["<b>Vertex AI Search</b><br/>Fund fact-sheet passages for the mix"]:::ext
    L --> M["<b>Gemini Pro</b><br/>Writes the proposal; every section cites<br/>a passage or the projection"]:::ai
    M --> N["<b>Core API</b><br/>Drops stray citations, checks every $ and %<br/>figure, runs the compliance check"]:::system
    N --> O["<b>Advisor</b><br/>Reviews the proposal, its 'verified' flag<br/>and compliance findings"]:::person

    E --> P["<b>Advisor</b><br/>Moves the lead along the pipeline:<br/>new → qualified → proposal → onboarding"]:::person
    I --> P
    O --> P
    P --> Q["<b>Core API</b><br/>Emits LeadStageChanged"]:::system

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

**Docs vs code**
- Atrium does not send the email; the advisor sends the reviewed draft from their own mail.
- A9 meeting brief and A11 call summary are not built (P1 and P2).

---

## 4. Convert to client

Code: `POST /leads/{id}/convert`, `services/conversion.py`.

```mermaid
flowchart TD
    A["<b>Advisor</b><br/>Clicks Convert on a lead"]:::person --> B{"<b>Core API</b><br/>Stage is qualified, proposal or onboarding?"}:::system
    B -- "no" --> X1["<b>Stop</b><br/>409, qualify the lead first<br/>(or it is already a client)"]:::stop
    B -- "yes" --> C{"<b>Core API</b><br/>Trust band high_risk or blocked?"}:::system
    C -- "yes" --> D{"<b>Advisor</b><br/>Gave an override reason?"}:::person
    D -- "no" --> X2["<b>Stop</b><br/>409, a documented reason is needed"]:::stop
    D -- "yes" --> E
    C -- "no" --> E{"<b>Core API</b><br/>Email already belongs to a person?"}:::system
    E -- "yes" --> X3["<b>Stop</b><br/>409, person exists"]:::stop
    E -- "no" --> F["<b>Core API</b><br/>Creates the investor (risk band from stated appetite)<br/>and an account ACC-nnnn; lead becomes client"]:::system
    F --> G["<b>Core API</b><br/>Records the conversion with Trust Score, band<br/>and reason; emits ClientOnboarded"]:::system
    G --> H["<b>Investor</b><br/>Can now complete a risk profile<br/>and invest (modules 5-9)"]:::person

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

**Notes:** the account's trading Trust Score (module 9) starts from the score the lead earned here. The override reason stays in Cloud SQL; the event only flags that one was recorded.

---

## 5. Risk profile conversation

Code: `routers/profile.py` (`GET/POST /me/risk-profile`, `POST /me/risk-profile/chat`), `services/risk_profile.py`.

```mermaid
flowchart TD
    A["<b>Investor</b><br/>Opens Portfolio → Risk profile"]:::person --> B{"<b>Investor</b><br/>Chat or questionnaire?"}:::person
    B -- "chat" --> C["<b>Investor</b><br/>Answers in their own words"]:::person
    C --> D["<b>Gemini Flash</b><br/>Fills the five fixed answers it can<br/>and asks for what is missing"]:::ai
    D --> E{"<b>Core API</b><br/>All five answers known?"}:::system
    E -- "no" --> C
    B -- "questionnaire" --> F["<b>Investor</b><br/>Picks the five answers"]:::person
    E -- "yes" --> G["<b>Risk-profile rules</b><br/>Band 1-5 = the lower of capacity<br/>(horizon, withdrawals) and tolerance<br/>(largest fall, reaction, experience)"]:::system
    F --> G
    G --> H["<b>Web</b><br/>Shows the band and the reasons"]:::web
    H --> I{"<b>Investor</b><br/>Confirm?"}:::person
    I -- "no" --> C
    I -- "yes" --> J["<b>Core API</b><br/>Saves the profile; nothing is saved before this"]:::system
    D -. "Gemini busy" .-> K["<b>Web</b><br/>503; the questionnaire is always there"]:::web

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

Gemini only collects answers; it never sets the band.

---

## 6. Insights: What-if, X-ray, Risk and fund reading

Code: `routers/invest.py`, `routers/insights.py`, `routers/funds.py`, `services/whatif.py`, `services/xray.py`, `services/risk_metrics.py`, `services/narrative.py`, `knowledge/fit.py`.

All four share one pattern: an engine computes, then Gemini may explain, and its figures are checked against the engine.

```mermaid
flowchart TD
    A["<b>Investor</b><br/>Opens Plan ahead, X-ray, Risk or a fund page"]:::person --> B{"<b>Investor</b><br/>Which one?"}:::person
    B -- "What-if" --> C["<b>What-if engine</b><br/>10,000 Monte Carlo paths over month-end<br/>history since 2007: median, range, chance of loss, fees"]:::system
    B -- "X-ray" --> D["<b>X-ray engine</b><br/>Look-through from funds and ETFs to companies,<br/>sectors, regions; overlap; fee drag"]:::system
    B -- "Risk" --> E["<b>Risk engine</b><br/>Volatility, beta, drawdown, VaR, Sharpe,<br/>drift against the risk profile"]:::system
    B -- "Fund" --> F["<b>Core API</b><br/>Fund explainer from the fact sheet,<br/>suitability against the band computed"]:::system
    C --> G["<b>Web</b><br/>Shows the numbers and charts at once"]:::web
    D --> G
    E --> G
    F --> G
    G --> H{"<b>Investor</b><br/>Asks for the explanation or<br/>'is it right for you?'"}:::person
    H -- "What-if, X-ray, Risk" --> I["<b>Gemini Flash</b><br/>Writes a plain-English reading of the facts"]:::ai
    H -- "Fund" --> J["<b>Vertex AI Search</b><br/>Retrieves fund document passages"]:::ext
    J --> K["<b>Gemini Flash</b><br/>Writes points for and against,<br/>each citing a passage"]:::ai
    I --> L["<b>Core API</b><br/>Checks every $ and % figure against the engine;<br/>drops uncited points; logs the decision"]:::system
    K --> L
    L --> M["<b>Web</b><br/>Shows the reading in serif, naming the model<br/>and whether the figures were checked"]:::web

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

**Docs vs code:** B5 stress tests, B9 proactive insights, B10 news digest and B12 statements and tax reports are not built (P1).

---

## 7. Fund orders (instructions) and monthly plans

Code: `routers/instructions.py`, `services/instructions.py`, `services/allocation.py`. Instruction states: `received → checked → accepted → priced → allocated → settled` (or `rejected`, `reversed`).

```mermaid
flowchart TD
    A["<b>Investor</b><br/>Chooses subscribe, redeem or switch,<br/>or a monthly plan"]:::person --> B["<b>Core API</b><br/>Preview: minimum, units held and not already<br/>promised, suitability against the band"]:::system
    B --> C{"<b>Core API</b><br/>Any check failed?"}:::system
    C -- "yes" --> X["<b>Stop</b><br/>Shows the failed check"]:::stop
    C -- "no" --> D{"<b>Core API</b><br/>Fund above the investor's risk band?"}:::system
    D -- "yes" --> E{"<b>Investor</b><br/>Acknowledges the extra risk?"}:::person
    E -- "no" --> X
    E -- "yes" --> F
    D -- "no" --> F["<b>Core API</b><br/>Accepts: steps received, checked, accepted;<br/>emits InstructionReceived; ledger untouched"]:::system
    F --> G["<b>Investor</b><br/>Subscriptions get a payment reference<br/>and wire the money"]:::person
    F --> H["<b>Day-end job</b><br/>Monthly plans due today become subscriptions"]:::system
    H --> I
    G --> R["<b>Operations</b><br/>Matches the payment on the bank statement<br/>(module 12)"]:::person
    F --> I{"<b>Day-end job</b><br/>Pricing guard: every fund priced and<br/>published for the dealing day? (cut-off 4 pm NY)"}:::system
    I -- "no" --> W["<b>Day-end job</b><br/>Waits; nothing is dealt"]:::system
    I -- "yes" --> J["<b>Ledger</b><br/>Posts units and cash at the published price:<br/>priced, then allocated"]:::system
    J --> K{"<b>Core API</b><br/>Subscription payment matched?"}:::system
    K -- "yes, or redeem / switch" --> L["<b>Core API</b><br/>Settled"]:::system
    K -- "not yet" --> M["<b>Core API</b><br/>Stays allocated until the match"]:::system
    R --> M
    M --> L

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

**Docs vs code:** B11 in the blueprint says instructions are pre-checked "by the Trust and Trade agents". In the code the pre-check is deterministic rules (minimum, holdings, suitability); no agent and no Trust Score is involved for fund orders.

---

## 8. Investor Copilot

Code: `POST /accounts/{id}/copilot`, `agents/investor.py`.

```mermaid
flowchart TD
    A["<b>Investor</b><br/>Clicks 'Ask Atrium' and asks a question"]:::person --> B["<b>Core API</b><br/>Checks the investor may see this account;<br/>takes a read-only snapshot"]:::system
    B --> C["<b>Investor Copilot agent</b><br/>(ADK, Gemini Flash) decides which tools to call"]:::ai
    C --> D["<b>Tools</b><br/>Holdings, valuation, X-ray, risk, fund orders,<br/>what-if, withdrawal preview, Guardian check"]:::system
    C --> E["<b>Vertex AI Search</b><br/>Fund document passages"]:::ext
    C --> F["<b>Yahoo Finance</b><br/>Quotes for holdings"]:::ext
    D --> C
    E --> C
    F --> C
    C --> G["<b>Core API</b><br/>Logs the decision and every tool call"]:::system
    G --> H["<b>Investor</b><br/>Reads the answer, opens the tool trace and sources"]:::person
    C -. "agent busy" .-> X["<b>Stop</b><br/>503, try again in a minute"]:::stop

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

Nothing inside the agent loop writes to the database; the copilot answers but never places an order.

---

## 9. Placing an order through the Pre-trade Guardian

Code: `routers/trading.py` (`/orders/preview`, `/orders/explain`, `/orders`, `/cancel`), `services/orders.py`, `services/guardian.py`, `services/account_trust.py`, `markets/broker.py`, `services/order_ai.py`.

```mermaid
flowchart TD
    A["<b>Investor</b><br/>Opens a stock or ETF, fills the order ticket:<br/>buy or sell, market or limit, quantity"]:::person --> B["<b>Yahoo Finance</b><br/>Live quote (1-minute cache; last close if unreachable)"]:::ext
    B --> C["<b>Core API</b><br/>Records the device; builds the account snapshot"]:::system
    C --> D["<b>Trust rules, stage 4</b><br/>New device, large sale, size against the account:<br/>possible takeover?"]:::system
    D --> E["<b>Guardian rules</b><br/>Risk profile, cash or shares, suitability,<br/>concentration (counting funds), sector, size,<br/>liquidity, market hours, wash sale, day trading, trust"]:::system
    E --> F["<b>Guardian rules</b><br/>One verdict: the worst check wins<br/>proceed · warn · hold · block"]:::system
    F --> G{"<b>Investor</b><br/>Wants it explained?"}:::person
    G -- "yes" --> H["<b>Gemini Flash</b><br/>Explains the order and the verdict;<br/>figures checked; it never changes the verdict"]:::ai
    G -- "no" --> I
    H --> I{"<b>Guardian</b><br/>Verdict?"}:::system
    I -- "block" --> X["<b>Stop</b><br/>Cannot be placed as it stands"]:::stop
    I -- "warn" --> J{"<b>Investor</b><br/>Acknowledges the warnings?"}:::person
    J -- "no" --> X2["<b>Stop</b><br/>Not placed"]:::stop
    J -- "yes" --> K
    I -- "proceed" --> K["<b>Investor</b><br/>Places the order (account holder only)"]:::person
    I -- "hold" --> K
    K --> L["<b>Core API</b><br/>Re-runs the Guardian under an account lock;<br/>emits OrderPlaced"]:::system
    L --> M{"<b>Core API</b><br/>Held?"}:::system
    M -- "yes" --> N["<b>Core API</b><br/>State held; emits OrderHeld<br/>→ Advisor queue (module 10)"]:::system
    M -- "no" --> O["<b>Broker</b><br/>Paper broker by default, or Alpaca paper API"]:::ext
    O --> P{"<b>Broker</b><br/>Filled?"}:::ext
    P -- "filled" --> Q["<b>Ledger</b><br/>Posts shares and cash, emits OrderFilled<br/>and TransactionPosted"]:::system
    P -- "resting (limit or market closed)" --> R["<b>Core API</b><br/>State open; refreshed when the<br/>investor lists orders"]:::system
    R --> P
    R -.-> S["<b>Investor</b><br/>May cancel an open order"]:::person
    P -- "rejected" --> T["<b>Core API</b><br/>State rejected, emits OrderRejected"]:::system

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

**Thresholds:** one company above 15% of the account warns, above 35% holds; a sector above 40% warns; an order above 25% of the account warns; above 1% of daily volume warns.

**Docs vs code**
- Blueprint C3 and §6.2 describe the Guardian as an **ADK agent** with Gemini reasoning. The code makes it **fixed rules only**, so the same order always gets the same verdict; Gemini explains (C4) and, for held orders, writes a review note (module 10).
- Blueprint C2 routes orders to Alpaca. The default is Atrium's own paper broker; Alpaca is used when its keys are set.
- C5 post-trade anomaly detection, C6 holding intelligence and C7 rebalancing are not built (P1).

---

## 10. Held-order review

Code: `GET /orders/held`, `POST /orders/{id}/review-note`, `/release`, `/reject`.

```mermaid
flowchart TD
    A["<b>Advisor</b><br/>Opens Held orders"]:::person --> B["<b>Web</b><br/>Shows each held order with the Guardian's<br/>checks and the trust signals"]:::web
    B --> C{"<b>Advisor</b><br/>Wants a review note?"}:::person
    C -- "yes" --> D["<b>Gemini Pro</b><br/>Writes a review note with a suggestion;<br/>figures checked (about 16 s)"]:::ai
    D --> E
    C -- "no" --> E{"<b>Advisor</b><br/>Release or reject? (note optional)"}:::person
    E -- "reject" --> F["<b>Core API</b><br/>State rejected, emits OrderRejected"]:::system
    E -- "release" --> G["<b>Guardian rules</b><br/>Re-checks the order now, under the account lock"]:::system
    G --> H{"<b>Guardian</b><br/>Any check now blocks?"}:::system
    H -- "yes" --> X["<b>Stop</b><br/>Can no longer go ahead"]:::stop
    H -- "no" --> I["<b>Core API</b><br/>Records who released it, emits OrderReleased"]:::system
    I --> J["<b>Broker</b><br/>Executes as in module 9"]:::ext
    J --> K["<b>Investor</b><br/>Sees the outcome in Your trades"]:::person
    F --> K

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

The release is the advisor's decision; the review note only suggests.

---

## 11. Day-end run

Code: `ops/day_end.py` (Cloud Run job `atrium-day-end`), `POST /operations/day-end`, `services/fund_pricing.py`, `services/allocation.py`, `services/aml.py`.

```mermaid
flowchart TD
    A["<b>Cloud Scheduler</b><br/>5:15 pm New York, weekdays"]:::ext --> C
    B["<b>Operations</b><br/>Starts the day-end from Today"]:::person --> C["<b>Day-end job</b><br/>Takes the operations lock; works on the<br/>last closed session"]:::system
    C --> D["<b>Day-end job</b><br/>1 Prices: drafts each fund's NAV from<br/>constituent closes (status draft)"]:::system
    D --> E["<b>Day-end job</b><br/>2 Monthly plans due → subscriptions"]:::system
    E --> F{"<b>Day-end job</b><br/>3 Pricing guard: all prices published?"}:::system
    F -- "no" --> G["<b>Day-end job</b><br/>Allocation waits; publishing needs<br/>four eyes (module 13)"]:::system
    F -- "yes" --> H["<b>Ledger</b><br/>Allocation deals accepted instructions"]:::system
    G --> I
    H --> I["<b>Day-end job</b><br/>4 Monitoring: AML scenarios + anomaly model<br/>→ alerts (module 14)"]:::system
    I --> J["<b>Day-end job</b><br/>5 Exceptions: money not arrived, stale receipts,<br/>unmatched lines, approvals waiting"]:::system
    J --> K["<b>Gemini Flash</b><br/>Writes the morning brief; figures checked"]:::ai
    K -. "unavailable" .-> L["<b>Day-end job</b><br/>Rule brief lists the steps"]:::system
    K --> M["<b>Day-end job</b><br/>Saves the run (ok or partial), emits DayEndCompleted"]:::system
    L --> M
    M --> N["<b>Operations</b><br/>Reads the brief and the steps on Today"]:::person

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

Each step records what it did; a failing step is recorded and the others still run. Because prices are only drafted here, allocation normally deals on the **next** run, after a second person has published them.

**Docs vs code:** blueprint §8.3 has the Compliance agent triage every alert during the day-end. In the code alerts are only raised here; the Gemini Pro review runs when the MLRO asks for it (module 14). The morning brief is for operations; the advisor pipeline brief (P8) is not built.

---

## 12. Bank statement intake and reconciliation

Code: `routers/operations.py` (`/statements`, `/statements/sample`, `/reconcile`, `/matches/*`), `services/statements.py`, `services/reconciliation.py`, `agents/reconciler.py`.

```mermaid
flowchart TD
    A["<b>Operations</b><br/>Opens Reconciliation"]:::person --> B{"<b>Operations</b><br/>Read the sample or upload a statement?"}:::person
    B -- "sample" --> C["<b>Core API</b><br/>Writes a sample statement for the payments<br/>Atrium is waiting for (CSV by default)"]:::system
    B -- "upload" --> D{"<b>Core API</b><br/>PDF or CSV, up to 10 MB?"}:::system
    D -- "no" --> X["<b>Stop</b><br/>413 or unsupported"]:::stop
    C --> E{"<b>Core API</b><br/>Format?"}:::system
    D -- "yes" --> E
    E -- "PDF" --> F["<b>Document AI</b><br/>Bank Statement Parser extracts the lines"]:::ext
    E -- "CSV" --> G["<b>Core API</b><br/>Parses the CSV"]:::system
    F --> H["<b>Gemini Flash</b><br/>Reads each narration: payer, quoted reference<br/>(typos kept), how the money came"]:::ai
    G --> H
    H -. "unavailable" .-> H2["<b>Core API</b><br/>Rule reading"]:::system
    H --> I["<b>Operations</b><br/>Checks counts and the balance; clicks Find matches"]:::person
    H2 --> I
    I --> J["<b>Reconciliation rules</b><br/>Exact reference + amount (0.99);<br/>unique amount from the holder (0.85)"]:::system
    J --> K["<b>Reconciliation agent</b><br/>(ADK, Gemini Flash) works what is left with scoring<br/>tools: fuzzy references, split payments"]:::ai
    K -. "agent fails" .-> K2["<b>Scorer</b><br/>Proposes the strongest candidates itself"]:::system
    K --> L["<b>Core API</b><br/>Proposals with tier, confidence and evidence;<br/>emits MatchProposed"]:::system
    K2 --> L
    L --> M{"<b>Operations</b><br/>Accept or reject each proposal<br/>('accept all exact matches')"}:::person
    M -- "accept" --> N["<b>Core API</b><br/>Funds the subscription: settled now if<br/>already allocated, else at allocation"]:::system
    M -- "reject" --> O["<b>Core API</b><br/>Lines return to unmatched, with the note"]:::system
    O --> P{"<b>Operations</b><br/>Match by hand?"}:::person
    P -- "yes" --> Q["<b>Operations</b><br/>Requests a manual match with a reason<br/>→ four eyes (module 13)"]:::person

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

The agent's tools check every id and amount, so it cannot use a line twice, claim a subscription that is not open, or propose a combination that does not add up. In the demo, operations can also add another set of waiting payments so each visitor has something to reconcile.

---

## 13. Four-eyes approvals

Code: `services/approvals.py`, `services/fund_pricing.py` (`request_publish`, `execute_publish`), `services/reconciliation.py` (manual match), `services/reversals.py`, `routers/me.py` (`/me/authenticator`).

```mermaid
flowchart TD
    A{"<b>Operations (requester)</b><br/>What needs changing?"}:::person
    A -- "publish draft prices" --> B["<b>Operations</b><br/>Asks to publish a day's prices, with a reason"]:::person
    A -- "manual match" --> C["<b>Operations</b><br/>Picks lines and subscriptions, with a reason"]:::person
    A -- "reverse a posting" --> D["<b>Operations</b><br/>Picks a fund subscription on the Blotter, with a reason"]:::person
    B --> E["<b>Core API</b><br/>Creates a pending approval: summary, evidence,<br/>payload hash; emits ApprovalRequested"]:::system
    C --> E
    D --> E
    E --> F["<b>Second approver</b><br/>Opens Approvals, reads the reason and evidence"]:::person
    F --> G["<b>Second approver</b><br/>Enters the six-digit code from the authenticator"]:::person
    G --> H{"<b>Core API</b><br/>Still pending? A different person?<br/>Ops or admin? Code valid? Payload unchanged?"}:::system
    H -- "any no" --> X["<b>Stop</b><br/>Refused with the reason<br/>(e.g. you cannot approve your own)"]:::stop
    H -- "approve" --> I{"<b>Core API</b><br/>Runs the action"}:::system
    I -- "prices" --> J["<b>Core API</b><br/>Prices published, emits PricePublished;<br/>allocation can run"]:::system
    I -- "match" --> K["<b>Core API</b><br/>Match accepted; subscriptions funded"]:::system
    I -- "reversal" --> L["<b>Ledger</b><br/>Reversing posting cancels units and cash;<br/>nothing is edited or deleted"]:::system
    H -- "reject" --> M["<b>Core API</b><br/>Rejected; a manual match frees its lines"]:::system
    J --> N["<b>Core API</b><br/>Records approver, time, step-up and note;<br/>emits ApprovalDecided"]:::system
    K --> N
    L --> N
    M --> N

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

**Docs vs code:** blueprint D6 also lists **bank-detail change** and **large redemption** as four-eyes actions. The code supports three: `publish_prices`, `manual_match`, `reverse_posting`. A reversal is allowed only for a fund subscription whose units are all still held.

---

## 14. AML monitoring and case decision

Code: `services/aml.py`, `ml/aml_model.py`, `services/compliance_ai.py`, `routers/compliance.py`.

```mermaid
flowchart TD
    A["<b>Day-end job</b><br/>Runs monitoring (or the MLRO runs it on demand)"]:::system --> B["<b>AML rules</b><br/>Structuring under $10,000, rapid in-out,<br/>third-party funding, linked round trip,<br/>velocity, dormant reactivation, high-risk country"]:::system
    A --> C["<b>k-means anomaly model</b><br/>Trained in BigQuery ML, scored locally<br/>from aml_model.json"]:::system
    B --> D["<b>Core API</b><br/>Raises each new alert once (fingerprint),<br/>with the exact rows as evidence; emits AlertRaised"]:::system
    C --> D
    D --> E["<b>MLRO</b><br/>Opens Alerts, sorted by severity"]:::person
    E --> F["<b>Core API</b><br/>Alert page: the finding, evidence rows,<br/>linked-entity graph (shared bank account by<br/>blind index, device, outside payer)"]:::system
    F --> G{"<b>MLRO</b><br/>Ask for a case review?"}:::person
    G -- "yes" --> H["<b>Gemini Pro</b><br/>Suggests a triage and drafts a SAR-style<br/>narrative citing evidence ids (16-21 s)"]:::ai
    H --> I["<b>Core API</b><br/>Drops citations to anything else,<br/>checks every $ and % figure, logs it"]:::system
    I --> J
    G -- "no" --> J{"<b>MLRO</b><br/>Escalate or close, with a note"}:::person
    J --> K["<b>Core API</b><br/>Records the decision and who made it"]:::system
    K --> L["<b>MLRO</b><br/>Decision log: every AI decision and<br/>every four-eyes approval"]:::person

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

**Docs vs code**
- Blueprint D7 runs the scenarios as SQL over BigQuery. The code runs them in Python over Cloud SQL; BigQuery is used to train the anomaly model and to receive events.
- Blueprint D8 and §6.2 call the Compliance copilot an ADK agent. The code makes one Gemini Pro call with the evidence; it has no tools.
- Bank-detail change followed by withdrawal (named in D7) is not among the scenarios. D9 KYC refresh and D12 report pack are not built.

---

## 15. AI decision log and event stream

Code: `ai/decisions.py`, `events.py`, `routers/ai.py` (`GET /ai/usage`), `GET /leads/{id}/decisions`, `GET /compliance/ai-decisions`.

```mermaid
flowchart LR
    A["<b>Any AI call</b><br/>Gemini Flash or Pro, ADK agent"]:::ai --> B["<b>Core API</b><br/>Writes the AI decision: agent, purpose, model,<br/>input digest, output, confidence, tokens, cost"]:::system
    B --> C[("<b>Cloud SQL</b><br/>ai_decisions")]:::system
    B --> D["<b>Event stream</b><br/>Metadata only, no personal data"]:::system
    E["<b>Core API services</b><br/>LeadCreated, TrustScoreChanged, OrderPlaced,<br/>MatchProposed, AlertRaised, ApprovalDecided, ..."]:::system --> D
    D --> F["<b>Pub/Sub</b><br/>(when enabled)"]:::ext
    F --> G[("<b>BigQuery</b><br/>atrium.events")]:::ext
    C --> H["<b>Advisor</b><br/>Lead's AI activity panel"]:::person
    C --> I["<b>MLRO</b><br/>Decision log"]:::person
    C --> J["<b>Staff</b><br/>AI usage and cost (/ai/usage)"]:::person

    classDef person fill:#DCEBFF,stroke:#1F5FAD,color:#0F1B24
    classDef web fill:#EEF0F2,stroke:#6B7680,color:#0F1B24
    classDef system fill:#E3F4EA,stroke:#157347,color:#0F1B24
    classDef ai fill:#FCEFD2,stroke:#E3A72F,color:#0F1B24
    classDef ext fill:#EFE4F8,stroke:#7A4BA8,color:#0F1B24
    classDef stop fill:#F8E1DC,stroke:#B23A26,color:#0F1B24
```

**Docs vs code:** blueprint D11 records the approver of each AI output. The AI log does not; approvals are in their own table and log. P3 (Cloud DLP redaction before text reaches a model) and P6 (evaluation harness) are not built.

---

## Summary: where the code differs from the blueprint

| Area | Blueprint says | Code does | Module |
|---|---|---|---|
| Lead scoring timing | Async agents fed by Pub/Sub | Inline in the capture request, plus a staff catch-up | 1 |
| Lead anomaly detection | BigQuery ML at the lead stage | Rule weights plus Gemini enrichment | 1 |
| Sanctions and PEP (A6) | P1 feature | Not built | 1 |
| ID upload | Prospect uploads with the form | Advisor uploads on the lead page | 2 |
| Fund-order pre-check (B11) | Trust and Trade agents | Deterministic rules | 7 |
| Pre-trade Guardian (C3) | ADK agent with Gemini reasoning | Fixed rules; Gemini only explains and writes review notes | 9, 10 |
| Broker (C2) | Alpaca paper | Own paper broker by default, Alpaca when keys are set | 9 |
| Concierge router | Routes across all seven agents | Routes between the two advisor agents only | 3 |
| Day-end triage | Compliance agent triages every alert | Alerts raised; Gemini Pro review on the MLRO's request | 11, 14 |
| AML scenarios (D7) | SQL over BigQuery | Python over Cloud SQL; BigQuery trains the model | 14 |
| Compliance copilot (D8) | ADK agent | Single Gemini Pro call, no tools | 14 |
| Four-eyes actions (D6) | Prices, manual match, bank-detail change, large redemption | Prices, manual match, ledger reversal | 13 |
| Admin workspace (P1) | Separate workspace | Admin uses the Advisor workspace | 0 |

Most of these are deliberate: the Guardian and the Trust Score were made rule-based so the same input always gives the same verdict, which the blueprint's own principle ("AI never changes a fact; it proposes") favours. They are listed so the deck and the video describe what the product actually does.
