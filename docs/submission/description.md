# Atrium: brief description

**Atrium is one AI-native platform for the whole client life of a wealth firm** (BFSI: Intelligent Risk, Fraud & Financial Experiences).

Wealth firms run each client on separate systems: one for leads, one for portfolios, one for trading and one for the books. Fraud slips through the gaps between them, and the AI bolted on top is a black box.

Atrium joins the four stages, **Acquire, Invest, Trade and Operate**, with compliance across all of them. One identity graph, one ledger and one decision log see everything:
- A device seen on a fraudulent lead is recognised when it signs in to a client's account.
- A sale from a browser the account has never used is held as a possible takeover.

Gemini works at every step, and a person makes every decision. Every figure Gemini writes is checked against Atrium's engines, every claim is cited, and a built-in Model Risk Office tests, attacks and logs every model.

## How we use Firebase, Firestore, Cloud Run and Gemini

**Gemini (3.1 Pro and 3.8 Flash on Vertex AI)**
- Explains risk, What-if simulations and orders, with every dollar and percentage checked against the engines.
- Writes proposals, held-order review notes and AML case reviews that may cite only the evidence.
- Listens to recorded client calls and flags conduct problems, quoting the second each was said.
- Turns a plain-English market scenario into shocks, grounded with Google Search.
- Runs our ADK agents: the Investor Copilot, the reconciliation agent and the advisor concierge.

**Cloud Run**
- Serves the Next.js web app and the FastAPI API.
- Runs two jobs: the day-end, started by Cloud Scheduler (fund prices, monthly plans, AML monitoring and Gemini's morning brief), and the live model checks that gate every release.

**Firebase**
- Hosting is the public front door (atrium-cup-2026.web.app), rewriting to Cloud Run.
- Firebase Authentication signs each person into their live inbox with a custom token that the API mints, carrying their person id as a claim.

**Cloud Firestore**
- Holds each person's live inbox. When the Pre-trade Guardian holds an order, an approval is requested or decided, an AML alert is raised, a lead is blocked, a circuit breaker trips or the day-end finishes, the API writes an item to people/{id}/inbox once the database work has committed.
- The browser listens with onSnapshot, so Daniel's bell lights up the moment Tom's suspicious sale is held.
- Security rules let each person read only their own inbox.

**Also in production**
- BigQuery ML: the Lead Score, and the AML anomaly model.
- Document AI: identity proofing and bank statements.
- Vertex AI Search: fund documents, with citations.
- Cloud SQL, plus Pub/Sub to BigQuery for events.

## Measured on the live deployment

- 37 of 37 live model-check suites passing on real Gemini.
- Red team: 29 of 29 fresh attacks resisted.
- Fair lending: 18 of 18 name pairs read the same.
- Lead Score: AUC 0.76 on 5,000 held-out leads.
- What-if: a 10,000-path Monte Carlo in 0.55 s.
- Tests: 699 API and 209 web tests passing.
