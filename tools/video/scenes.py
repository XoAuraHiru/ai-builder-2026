"""The full Atrium film, scene by scene: what the narrator says and what happens on screen, in the real app.

A scene is a list of beats. Each beat is one spoken sentence and what happens on screen while it is said; the next
beat starts when both the sentence and its action are done, so the voice never runs ahead of the screen, and each
beat ends with a short pause to read what appeared. Long Gemini waits are cut with a chip saying how long they took.

Everything Gemini writes on screen comes from the live deployment. The one action that changes data a judge will see
(approving a reversal with a one-time code) runs on a local copy of the app; on the live app the cursor rests on
decisions without making them.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import quote

CARDS = Path(__file__).resolve().parent / "cards"
LIVE = "https://atrium-web-tvflgkcdoa-uc.a.run.app"
LOCAL = "http://localhost:3000"
RUTH = "be8280f2e7fe43a883ed789e8c91b9c0"
JAMES = "2277fc5a7b394bc99607531821555e23"
GRACE = "aeb88ca6076f4125aa48109d6916a34e"
GEMINI_WAIT = "figure[role=status]"  # AiThinking, while Gemini works

Act = Callable[..., Awaitable[None]]


@dataclass
class Beat:
    text: str
    act: Act | None = None
    after: float = 0.8  # seconds on screen after the sentence, to read what appeared


@dataclass
class Scene:
    key: str
    beats: list[Beat]
    persona: str | None = None
    start: str = "/"
    ready: str | None = None
    base: str = LIVE
    label: tuple[str, str, str] | None = None
    settle: float = 1.2
    tail: float = 0.6
    cursor: bool = True
    extra: dict = field(default_factory=dict)


def chapter(n: int, title: str, line: str, who: list[tuple[str, str]], kicker: str = "STAGE", of: int = 4) -> str:
    people = ";".join(f"{name}|{role}" for name, role in who)
    return (CARDS / "chapter.html").as_uri() + (f"#n={n}&of={of}&kicker={quote(kicker)}&title={quote(title)}"
                                                f"&line={quote(line)}&who={quote(people)}")


def hold(seconds: float) -> Act:
    async def act(r):
        await r.hold(seconds)
    return act


async def ai(r, chip: str, linger: float = 2.2, timeout: float = 180) -> None:
    """Let the Gemini panel be seen, then cut to its answer with a chip saying how long it took."""
    await r.hold(linger)
    await r.cut_wait(sel=GEMINI_WAIT, gone=True, timeout=timeout, chip=chip)


# -- opening -----------------------------------------------------------------------------------------------------

async def front_plan(r):
    await r.hold(1.0)
    for stage in ("Acquire", "Invest", "Trade", "Operate"):
        await r.move_to(text=stage, sel="h3, h2, p, span, div", exact=True)
        await r.hold(0.5)


async def analyzer_open(r):
    await r.scroll_to(text="See what your money could become", at=0.12, ms=1300)


async def analyzer_run(r):
    await r.click(text="Unit trust (Atrium fund)")
    await r.wait_for(text="Balanced", sel="[role=radio]")
    await r.click(text="Balanced", sel="[role=radio]")
    await r.click(sel="input[aria-label='One-time amount']")
    await r.select_all("input[aria-label='One-time amount']")
    await r.type("10000", per_char=0.09)
    await r.click(sel="input[aria-label='Every month']")
    await r.select_all("input[aria-label='Every month']")
    await r.type("250", per_char=0.09)
    await r.click(text="Analyze", sel="button[type=submit]", exact=True)  # the form's button, not the header link
    await r.cut_wait(text="Middle outcome", timeout=90, chip="10,000 futures simulated in {s} s")
    await r.scroll_to(text="Middle outcome", at=0.2, ms=1100)


async def analyzer_apply(r):
    await r.move_to(text="Likely range")
    await r.hold(0.8)
    await r.move_to(text="Talk to an advisor about this plan")


# -- acquire -----------------------------------------------------------------------------------------------------

async def leads_scores(r):
    await r.hold(0.8)
    await r.move_to(text="Look at these first")
    await r.hold(0.6)
    await r.move_to(text="fit 53")


async def leads_ring(r):
    await r.move_to(text="Many leads from one device")
    await r.hold(0.6)
    await r.move_to(text="Disposable email domain")


async def leads_ids(r):
    await r.move_to(text="Possible image manipulation")


async def james_doc(r):
    await r.scroll_to(text="Identity document", at=0.12, ms=1200)
    await r.move_to(text="Possible image manipulation")


async def james_name(r):
    await r.move_to(text="Name does not match the form")


async def ruth_score(r):
    await r.hold(0.4)
    await r.click(text="Score this lead")
    await ai(r, "Scored in {s} s", linger=1.8)
    await r.move_to(text="Lead Score", sel="h3")


async def ruth_call(r):
    await r.scroll_to(text="Gemini listens to a recorded call", at=0.2, ms=1200)
    await r.click(text="Analyse the pressure call")
    await ai(r, "Gemini listened to the 2½-minute call in {s} s · the wait is shortened", linger=2.6)
    await r.scroll_by(300, 1100)


async def ruth_flags(r):
    await r.move_to(text="Third party directing the client", sel="span, div")
    await r.hold(1.0)
    await r.move_to(text="Guarantee or promise", sel="span, div")
    await r.hold(1.0)
    await r.move_to(text="High · Pressure", sel="span, div")


async def ruth_ground(r):
    await r.move_to(sel="button[aria-label*='Guarantee']")  # the play button of the guarantee flag


async def grace_proposal(r):
    await r.scroll_to(text="Gemini Pro writes a personalised proposal", at=0.2, ms=1200)
    await r.click(text="Write a proposal")
    await ai(r, "Gemini Pro wrote the proposal in {s} s · the wait is shortened", linger=2.6)
    await r.scroll_by(260, 1100)


async def grace_read(r):
    await r.scroll_by(420, 2600)
    await r.hold(1.0)


# -- invest ------------------------------------------------------------------------------------------------------

async def home_value(r):
    await r.hold(0.6)
    await r.move_to(text="on what you paid in")
    await r.hold(0.4)
    await r.move_to(text="One thing needs your attention")


async def home_drift(r):
    await r.move_to(text="Your profile", sel="span, div")
    await r.hold(0.8)
    await r.move_to(text="Your portfolio now", sel="span, div")


async def whatif_fan(r):
    await r.hold(0.8)
    await r.move_to(text="After 15 years", sel="h2")
    await r.hold(0.6)
    await r.scroll_by(240, 1100)


async def whatif_explain(r):
    await r.scroll_to(text="What this means for you", at=0.15, ms=1100)
    await r.click(text="Explain these results")
    await ai(r, "Gemini explained it in {s} s", linger=1.6)


async def xray_look(r):
    await r.hold(0.6)
    await r.move_to(text="Things to look at")


async def xray_nvda(r):
    await r.move_to(text="Three companies are each a large share")
    await r.hold(0.8)
    await r.scroll_to(text="Largest companies you own", at=0.15, ms=1200)
    await r.move_to(text="NVIDIA Corp")


async def scen_history(r):
    await r.hold(0.6)
    await r.scroll_to(text="History", sel="h2", at=0.12, ms=1200)
    await r.move_to(text="The 2008 financial crisis")


async def scen_type(r):
    await r.scroll_to(text="Your scenario", sel="h2", at=0.14, ms=1100)
    await r.click(sel="input[placeholder^='Oil at'], textarea[placeholder^='Oil at']")
    await r.type("Oil reaches $150 a barrel and the US enters a recession", per_char=0.04)


async def scen_map(r):
    await r.click(text="See what it could do")
    await ai(r, "Gemini searched the news and proposed the shocks in {s} s · shortened", linger=2.6)
    await r.hold(0.8)
    await r.scroll_to(text="The shocks", sel="h2", at=0.12, ms=1200)
    await r.move_to(text="Energy", sel="span, div, p")


async def fund_ask(r):
    await r.scroll_to(text="Is it right for you?", sel="h2", at=0.15, ms=1200)
    await r.click(text="Ask Gemini whether it fits me")
    await ai(r, "Vertex AI Search and Gemini answered in {s} s", linger=2.0)


async def fund_cites(r):
    await r.scroll_by(200, 1000)
    await r.hold(1.0)


async def copilot_ask(r):
    await r.hold(0.4)
    await r.click(text="What would the Guardian say if I bought 10 shares of NVIDIA?")
    await ai(r, "The Copilot agent answered in {s} s", linger=2.0, timeout=150)


async def copilot_read(r):
    await r.scroll_by(260, 1200)
    await r.hold(1.0)


# -- trade -------------------------------------------------------------------------------------------------------

async def nvda_market(r):
    await r.hold(0.6)
    await r.move_to(text="Delayed price from Yahoo Finance", sel="span, p, div")


async def nvda_check(r):
    await r.click(sel="input[inputmode=numeric]")
    await r.c.js("(() => { const i = document.querySelector('input[inputmode=numeric]'); i.select && i.select(); })()")
    await r.type("60", per_char=0.14)
    await r.click(text="Check order")
    await ai(r, "The Guardian checked and Gemini explained in {s} s", linger=1.4, timeout=120)


async def nvda_hold(r):
    await r.move_to(text="Suitability", sel="span, p, div, h3, b, strong")
    await r.hold(1.0)
    await r.move_to(text="Concentration", sel="span, p, div, h3, b, strong")


async def tom_sell(r):
    await r.hold(0.4)
    await r.click(text="Sell", exact=True)
    await r.click(sel="input[inputmode=numeric]")
    await r.c.js("(() => { const i = document.querySelector('input[inputmode=numeric]'); i.select && i.select(); })()")
    await r.type("120", per_char=0.14)
    await r.click(text="Check order")
    await ai(r, "The Guardian checked in {s} s", linger=1.4, timeout=120)


async def tom_hold(r):
    await r.move_to(text="Account trust", sel="span, p, div, h3, b, strong")


async def held_note(r):
    await r.scroll_to(text="Review note", sel="h2", at=0.15, ms=1200)
    await r.click(text="Ask Gemini Pro for a review note")
    await ai(r, "Gemini Pro wrote the note in {s} s · the wait is shortened", linger=2.4)
    await r.move_to(text="Release the order")


# -- operate -----------------------------------------------------------------------------------------------------

async def today_run(r):
    await r.hold(0.6)
    await r.scroll_to(text="Step log", sel="h2", at=0.15, ms=1200)


async def today_brief(r):
    await r.scroll_to(text="Draft prices", sel="h2", at=0.15, ms=1100)
    await r.move_to(text="Ask for publication")


async def recon_read(r):
    await r.hold(0.8)
    await r.move_to(text="Transactions read")
    await r.hold(0.6)
    await r.move_to(text="Matched")


async def recon_propose(r):
    await r.scroll_to(text="Proposals to decide", at=0.12, ms=1200)
    await r.move_to(text="Gemini proposal")
    await r.hold(1.0)
    await r.move_to(text="Proposed by the reconciliation agent")
    await r.hold(0.6)
    await r.move_to(text="Accept the match", exact=True)  # decided by a person; not clicked on the live demo


async def approve_code(r):
    code = await r.scene.extra["code"]()  # the authenticator code now, since codes change every 30 seconds
    await r.scroll_to(text="Code from your authenticator", at=0.45, ms=900)
    await r.click(sel="input[autocomplete='one-time-code'], input[inputmode=numeric]", pause_after=0.2)
    await r.type(code, per_char=0.14)
    await r.hold(0.4)
    await r.click(text="Approve", exact=True)
    await r.hold(1.4)


# -- protect and govern ------------------------------------------------------------------------------------------

async def alerts_list(r):
    await r.hold(0.6)
    await r.move_to(text="5 open alerts wait for a decision", sel="h2")
    await r.hold(0.6)
    await r.click(text="Possible structuring", sel="a")
    await r.cut_wait(text="Case review", timeout=60)


async def alert_chart(r):
    await r.move_to(text="reporting threshold", sel="span, div, text, p")  # the line the payments stop just under
    await r.hold(1.2)
    await r.scroll_to(text="Evidence", sel="h2", at=0.3, ms=1400)


async def alert_review(r):
    await r.scroll_to(text="Case review", sel="h2", at=0.1, ms=1200)
    await r.hold(1.2)
    await r.move_to(text="Escalate", exact=True)


async def rings_graph(r):
    await r.hold(0.6)
    await r.scroll_to(text="How they connect", at=0.12, ms=1200)


async def rings_device(r):
    await r.move_to(text="Sofia Rossi", sel="svg text, text")


async def rings_explain(r):
    await r.click(text="Explain this ring")
    await r.cut_wait(sel=GEMINI_WAIT, gone=True, timeout=90, chip="Gemini read the ring in {s} s")
    await r.hold(0.6)
    await r.scroll_to(text="Point at a link id", at=0.1, ms=1200)


async def models_inventory(r):
    await r.hold(0.6)
    await r.scroll_to(text="Inventory", at=0.15, ms=1200)


async def models_card(r):
    await r.click(text="Case review", sel="a, td, tr, div")
    await r.cut_wait(text="Golden cases", timeout=60)
    await r.hold(0.6)


async def models_redteam(r):
    await r.scroll_to(text="Red team", at=0.12, ms=1300)
    await r.hold(0.8)


async def log_table(r):
    await r.hold(0.6)
    await r.scroll_to(text="AI decisions", sel="h2", at=0.15, ms=1200)
    await r.hold(0.8)


# -- the film ----------------------------------------------------------------------------------------------------

B = Beat
SCENES: list[Scene] = [
    Scene("open", [B("Wealth firms run on separate systems: one for leads, one for portfolios, one for trading, and "
                     "one for the books.", hold(0.5)),
                   B("Fraud slips through the gaps between them, and the AI bolted on top is a black box.", hold(0.5),
                     after=1.4)],
          start=(CARDS / "open.html").as_uri(), ready="Atrium", settle=0.0, cursor=False),
    Scene("front", [B("Atrium is one AI-native platform for the whole client life, from the first enquiry to a "
                      "reconciled ledger.", hold(1.0)),
                    B("Four stages, eight people, and Gemini at every step, always checked against the numbers it "
                      "explains.", front_plan)],
          start="/", ready="A wealth firm run by", settle=0.0),
    Scene("analyzer", [B("Anyone can start without signing in.", analyzer_open),
                       B("The return analyzer replays ten thousand futures from real market history since 2007, with "
                         "the S&P 500 beside every share.", analyzer_run, after=1.2),
                       B("A visitor sees the likely range, and the plan becomes an application to an advisor, with "
                         "the figures attached.", analyzer_apply, after=1.2)],
          start="/", ready="See what your money could become", label=("00", "Before sign-in", "Return analyzer")),

    Scene("ch-acquire", [B("First, acquire. Daniel is an advisor, and Atrium checks every lead before he calls.",
                           hold(0.5), after=1.0)],
          start=chapter(1, "Acquire", "Every lead scored for fit and for fraud before an advisor calls.",
                        [("Daniel Okafor", "Advisor")]), ready="Acquire", settle=0.0, cursor=False),
    Scene("leads", [B("Every lead is scored twice: for fit, with BigQuery ML, and for trust, from fraud signals in the "
                      "form itself.", leads_scores),
                    B("The riskiest come first. Four leads arrived from one device within a day, each with a "
                      "throwaway email address.", leads_ring),
                    B("And two identity documents failed their checks.", leads_ids)],
          persona="daniel@atrium.demo", start="/advisor", ready="Look at these first",
          label=("01", "Acquire", "Lead Score and Trust Score")),
    Scene("identity", [B("On James's application, Document AI's identity proofing found signs of image manipulation.", james_doc),
                       B("And the name doesn't match the form, so the lead is blocked until a person checks it.",
                         james_name, after=1.2)],
          persona="daniel@atrium.demo", start=f"/advisor/leads/{JAMES}", ready="James Patel",
          label=("01", "Acquire", "Identity check")),
    Scene("score", [B("Ruth Alvarez is a new referral.", hold(0.8)),
                    B("One click scores her: Gemini reads her answers, BigQuery ML scores her fit, and the Trust "
                      "Score adds its signals.", ruth_score, after=1.2)],
          persona="daniel@atrium.demo", start=f"/advisor/leads/{RUTH}", ready="Ruth Alvarez",
          label=("01", "Acquire", "Scoring a lead")),
    Scene("call", [B("Her first call was recorded, and Gemini listens to it the way a compliance officer would.", ruth_call),
                   B("It finds a nephew directing her money, a promise of eight percent a year, and pressure to sign "
                     "this week.", ruth_flags, after=1.0),
                   B("Each flag quotes the transcript with the second it was said; what Gemini cannot ground is "
                     "dropped.", ruth_ground, after=1.2)],
          persona="daniel@atrium.demo", start=f"/advisor/leads/{RUTH}", ready="Ruth Alvarez",
          label=("01", "Acquire", "Call intelligence")),
    Scene("proposal", [B("For a lead who fits, Gemini Pro writes a personalised proposal from the simulation and the "
                         "fund documents.", grace_proposal),
                       B("Every figure is checked and every claim is cited. It is a draft for the advisor; nothing is "
                         "sent.", grace_read, after=1.0)],
          persona="daniel@atrium.demo", start=f"/advisor/leads/{GRACE}", ready="Grace Holloway",
          label=("01", "Acquire", "Proposal")),

    Scene("ch-invest", [B("Next, invest. Priya and Lucas are investors.", hold(0.5), after=1.0)],
          start=chapter(2, "Invest", "Portfolios tested against 10,000 futures drawn from real markets since 2007.",
                        [("Priya Raman", "Investor"), ("Lucas Moreau", "Investor")]),
          ready="Invest", settle=0.0, cursor=False),
    Scene("home", [B("Priya's home shows her portfolio, and the one thing that needs her attention.", home_value),
                   B("Her mix now behaves like risk band four, above the band three she chose with Gemini.", home_drift, after=1.2)],
          persona="priya@atrium.demo", start="/investor", ready="Your portfolio", settle=0.2,
          label=("02", "Invest", "Home and risk profile")),
    Scene("whatif", [B("What-if Studio tests her plan against ten thousand futures drawn from real markets.", whatif_fan),
                     B("Gemini explains the range, and every figure it writes is checked against the engine.", whatif_explain, after=1.4)],
          persona="priya@atrium.demo", start="/investor/what-if", ready="After 15 years",
          label=("02", "Invest", "What-if Studio")),
    Scene("xray", [B("Lucas's X-ray looks through his funds to the companies underneath.", xray_look),
                   B("About a tenth of his money is NVIDIA, held through six different ETFs.", xray_nvda, after=1.2)],
          persona="lucas@atrium.demo", start="/investor/xray", ready="Things to look at",
          label=("02", "Invest", "Portfolio X-ray")),
    Scene("scenarios", [B("Scenario Studio replays the hardest markets since 2007 on what Priya holds.",
                          scen_history),
                        B("Or she describes her own scenario, in plain English.", scen_type),
                        B("Gemini, grounded with Google Search, proposes the shocks; Atrium's engine prices them, and "
                          "she can change every one.", scen_map, after=1.2)],
          persona="priya@atrium.demo", start="/investor/scenarios", ready="2008 financial crisis",
          label=("02", "Invest", "Scenario Studio")),
    Scene("fundfit", [B("On any fund, Priya can ask whether it fits her.", fund_ask),
                      B("Gemini answers from her profile and the fact sheet, citing what Vertex AI Search found.", fund_cites, after=1.2)],
          persona="priya@atrium.demo", start="/investor/funds/ATR-BAL", ready="Is it right for you?",
          label=("02", "Invest", "Fund fit, cited")),
    Scene("copilot", [B("And the Investor Copilot, an agent built with ADK, answers in her own figures.",
                        copilot_ask),
                      B("Here it asks the Pre-trade Guardian before she places anything.", copilot_read, after=1.2)],
          persona="priya@atrium.demo", start="/investor/copilot", ready="Try asking",
          label=("02", "Invest", "Investor Copilot")),

    Scene("ch-trade", [B("Then, trade.", hold(0.5), after=1.0)],
          start=chapter(3, "Trade", "Every order checked before it reaches the market, and held when it looks wrong.",
                        [("Priya Raman", "Investor"), ("Tom Becker", "Investor"), ("Daniel Okafor", "Advisor")]),
          ready="Trade", settle=0.0, cursor=False),
    Scene("nvda", [B("Atrium trades real US stocks and ETFs at live prices, with paper money.", nvda_market),
                   B("Before any order reaches the market, the Pre-trade Guardian checks it.", nvda_check),
                   B("Sixty NVIDIA shares would take Priya two bands past her profile, so it holds the order for an "
                     "advisor, and says why.", nvda_hold, after=1.2)],
          persona="priya@atrium.demo", start="/investor/markets/NVDA", ready="Check order",
          label=("03", "Trade", "Pre-trade Guardian")),
    Scene("takeover", [B("Tom signs in from a browser his account has never used, and tries to sell his whole Tesla "
                         "position.", tom_sell),
                       B("A new device and a sale that large look like an account takeover, so the Guardian holds "
                         "this one too.", tom_hold, after=1.2)],
          persona="tom@atrium.demo", start="/investor/markets/TSLA", ready="Check order",
          label=("03", "Trade", "Account takeover")),
    Scene("held", [B("Held orders wait for an advisor.", hold(0.8)),
                   B("Gemini Pro writes a review note from what the Guardian checked, and Daniel releases or rejects "
                     "the order, with a reason.", held_note, after=1.2)],
          persona="daniel@atrium.demo", start="/advisor/held", ready="Held orders",
          label=("03", "Trade", "Held orders")),

    Scene("ch-operate", [B("Then, operate: the back office.", hold(0.5), after=1.0)],
          start=chapter(4, "Operate", "Statements reconciled, alerts reviewed, and two people for every change to "
                        "the books.", [("Mei Tanaka", "Operations"), ("Sam Ortiz", "Operations")]),
          ready="Operate", settle=0.0, cursor=False),
    Scene("today", [B("Each evening the day-end job drafts fund prices, runs monthly plans and AML monitoring, and "
                      "Gemini writes a morning brief.", today_run),
                    B("Publishing the prices needs a second person.", today_brief, after=1.0)],
          persona="mei@atrium.demo", start="/operations", ready="Step log",
          label=("04", "Operate", "Day-end")),
    Scene("recon", [B("Reconciliation turns chores into proposals.", recon_read),
                    B("Document AI reads the bank statement, an ADK agent proposes the matches rules can't make, and "
                      "a person decides each one.", recon_propose, after=1.2)],
          persona="mei@atrium.demo", start="/operations/reconciliation", ready="Proposals to decide",
          label=("04", "Operate", "Reconciliation")),
    Scene("approve", [B("Changing the books takes a second person and a one-time code.", approve_code, after=1.0)],
          persona="sam@atrium.demo", start="/operations/approvals", ready="Approve", base=LOCAL,
          label=("04", "Operate", "Two-person approval")),

    Scene("ch-govern", [B("Across all four stages, compliance watches for financial crime, and every model is "
                          "governed.", hold(0.5), after=1.0)],
          start=chapter(5, "Protect and govern", "Financial crime caught with its evidence, and every model "
                        "validated, attacked and watched.", [("Omar Haddad", "Compliance")],
                        kicker="ACROSS ALL FOUR STAGES"),
          ready="Protect and govern", settle=0.0, cursor=False),
    Scene("alert", [B("Seven AML scenarios and a BigQuery ML anomaly model raise alerts with the exact rows behind "
                      "them.", alerts_list),
                    B("Here, three subscriptions in five days, each just under the ten-thousand-dollar reporting "
                      "line.", alert_chart, after=1.0),
                    B("Gemini Pro reviews the case citing only its evidence; a tripwire stops payment text that tries "
                      "to steer it, and the MLRO decides.", alert_review, after=1.2)],
          persona="omar@atrium.demo", start="/compliance", ready="Possible structuring",
          label=("05", "Protect", "AML alerts and case review")),
    Scene("rings", [B("One identity graph runs across the whole lifecycle.", rings_graph),
                    B("Those four leads share a device that also signs in to a client flagged for money in and "
                      "straight out.", rings_device, after=1.0),
                    B("Gemini explains the ring, citing only the graph's real links.", rings_explain, after=1.4)],
          persona="omar@atrium.demo", start="/compliance/rings", ready="The strongest ring",
          label=("05", "Protect", "Fraud ring radar")),
    Scene("models", [B("In the Model Risk Office, every model has an owner, a risk tier and evidence.",
                       models_inventory),
                     B("Golden tests gate each deploy; then live checks, a red team and fair-lending tests run against "
                       "Gemini itself.", models_card),
                     B("When the red team steered a case review into closing an alert, its circuit breaker paused "
                       "it, until a tripwire made that impossible.", models_redteam, after=1.2)],
          persona="omar@atrium.demo", start="/compliance/models", ready="Inventory", settle=0.4,
          label=("05", "Govern", "Model Risk Office")),
    Scene("log", [B("And every AI decision, with its model, its cost and who acted on it, lands in one log.", log_table, after=1.0)],
          persona="omar@atrium.demo", start="/compliance/log", ready="AI decisions",
          label=("05", "Govern", "Decision log")),

    Scene("close", [B("Atrium runs on Gemini, ADK, Document AI, Vertex AI Search and BigQuery, on Cloud Run.", hold(0.5)),
                    B("People decide. The AI shows its working.", hold(0.5), after=2.0)],
          start=(CARDS / "close.html").as_uri(), ready="People decide.", settle=0.0, cursor=False),
]
