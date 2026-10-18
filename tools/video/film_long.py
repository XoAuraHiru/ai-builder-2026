"""The extended walkthrough: the short film's story, with the unit trust journey and the back office in full.

Every scene the short film (film_short.py) already recorded is reused here unchanged: same key, same words, so its
footage is copied over before this film is assembled. The scenes below that are new to this film are recorded
fresh. Chapters follow the short film: unit trusts, stocks, acquire, protect and govern.
"""
import film_short as f
import scenes as s
from scenes import GRACE, Beat as B, Scene, ai, hold

PRIYA, MEI, DANIEL, OMAR = f.PRIYA, f.MEI, f.DANIEL, f.OMAR


# -- fresh scenes ------------------------------------------------------------------------------------------------

async def funds_seven(r):
    await r.hold(0.5)
    await r.move_to(text="Atrium Cash Reserve")
    await r.hold(0.5)
    await r.move_to(text="Average a year")
    await r.hold(0.4)
    await r.move_to(text="Yearly cost")
    await r.hold(0.4)
    await r.move_to(text="Atrium Technology")


async def balanced_inside(r):
    await r.hold(0.4)
    await r.scroll_to(text="Growth of $10,000", at=0.15, ms=1100)
    await r.hold(0.8)
    await r.scroll_to(text="Year by year", at=0.15, ms=1100)
    await r.hold(0.6)
    await r.scroll_to(text="What it holds", at=0.15, ms=1100)
    await r.move_to(text="Largest companies underneath")
    await r.hold(0.5)


async def monthly_plan(r):
    await r.hold(0.3)
    await r.scroll_to(text="Add monthly plan", at=0.2, ms=1100)
    await r.move_to(text="Add monthly plan")
    await r.hold(0.6)
    await r.scroll_by(360, 1000)
    await r.hold(0.6)


async def draft_prices(r):
    await r.hold(0.4)
    await r.scroll_to(text="Step log", sel="h2", at=0.15, ms=1000)
    await r.hold(0.5)
    await r.scroll_to(text="Draft prices", sel="h2", at=0.15, ms=1000)
    await r.move_to(text="Atrium Balanced")
    await r.hold(0.6)


async def blotter(r):
    await r.hold(0.4)
    await r.move_to(text="Instruction", sel="th, span, div")
    await r.hold(0.4)
    await r.scroll_by(420, 1100)
    await r.move_to(text="Ask for a reversal")
    await r.hold(0.6)


async def risk_report(r):
    await r.hold(0.4)
    await r.move_to(text="In numbers", sel="h2")
    await r.hold(0.4)
    await r.scroll_to(text="Where the risk comes from", at=0.12, ms=1000)
    await r.hold(0.6)
    await r.scroll_to(text="How your funds move together", at=0.15, ms=1000)


async def risk_explain(r):
    await r.scroll_to(text="What this means for you", at=0.15, ms=1000)
    await r.click(text="Explain my risk")
    await ai(r, "Gemini explained it in {s} s", linger=1.4)


async def proposal_read(r):
    await r.scroll_to(text="Proposal", sel="h2", at=0.12, ms=1100)
    await r.hold(0.5)
    await r.scroll_by(420, 1400)
    await r.hold(0.5)


async def proposal_cited(r):
    await r.camera(text="Written by Gemini", sel="span, div, p, b, strong", zoom=1.12, ms=800)
    await r.hold(1.2)
    await r.camera_out(ms=700)
    await r.scroll_by(500, 1400)
    await r.hold(0.4)


async def honest_log(r):
    await r.hold(0.4)
    await r.scroll_to(text="AI decisions", sel="h2", at=0.15, ms=1000)
    await r.hold(0.6)


async def honest_rows(r):
    await r.move_to(text="Cost", sel="th, span, div")
    await r.hold(0.6)
    await r.scroll_by(320, 1100)
    await r.hold(0.6)


# -- the film ----------------------------------------------------------------------------------------------------

SHARED = {sc.key: sc for sc in f.SCENES}  # recorded once for the short film; copied into this film


def shared(key: str) -> Scene:
    return SHARED[key]


SCENES: list[Scene] = [
    shared("hook"),
    Scene("front", [B("One product, four workspaces, eight people. The story line at the top of every page says what "
                      "to try next, and Gemini explains beside every number it writes.", s.front_plan, after=0.5)],
          start="/", ready="A wealth firm run by", settle=0.0, lower=("One platform", "Four workspaces · eight people")),

    shared("ch1"),
    f.ANALYZER,
    shared("pool"),
    Scene("funds7", [B("Atrium runs seven funds, from Cash Reserve at band one to Technology at band five. Each is a "
                       "fixed mix of low-cost ETFs, rebalanced monthly, with one yearly fee and no entry, exit or "
                       "switching fees.", funds_seven, after=0.5)],
          persona=PRIYA, start="/investor/funds", ready="Funds", lower=("Seven funds", "One fee · no entry or exit fees")),
    Scene("balanced", [B("Balanced is sixty percent US stocks and forty percent bonds. Priya sees its unit price since "
                         "2007, how ten thousand dollars would have grown, each year's return, and the companies "
                         "underneath.", balanced_inside, after=0.5)],
          persona=PRIYA, start="/investor/funds/ATR-BAL", ready="Growth of $10,000",
          lower=("Inside a fund", "Unit price since 2007 · look-through")),
    shared("fund"),
    shared("subscribe"),
    Scene("monthly", [B("A monthly plan pays in on the day she chooses, exempt from the fund's minimum, and every "
                        "contribution shows up in her order history.", monthly_plan, after=0.5)],
          persona=PRIYA, start="/investor/orders", ready="Add monthly plan", lower=("Monthly plan", "Fund orders")),
    Scene("drafts", [B("Each evening the day-end drafts every fund's unit price from its ETFs' closes, and checks each "
                       "move against the rules before anyone sees it.", draft_prices, after=0.5)],
          persona=MEI, start="/operations", ready="Step log", lower=("Draft prices", "Day-end job · Cloud Scheduler")),
    shared("price"),
    shared("publish"),
    shared("allocate"),
    Scene("blotter", [B("The blotter is the firm's record: every instruction, its price, its posting and any reversal, "
                        "each with who asked and who approved.", blotter, after=0.5)],
          persona=MEI, start="/operations/blotter", ready="Blotter", lower=("The blotter", "Every instruction and reversal")),
    Scene("risk", [B("Her risk report shows volatility, the worst drawdown since 2007, where the risk comes from, and "
                     "how her funds move together.", risk_report),
                   B("Gemini explains it, every figure from the engine.", risk_explain, after=0.6)],
          persona=PRIYA, start="/investor/risk", ready="In numbers", lower=("Risk report", "Engine figures · Gemini explains")),
    Scene("whatif", [B("What-if Studio tests her plan against ten thousand futures drawn from real markets.", s.whatif_fan),
                     B("Gemini explains the range, and every figure it writes is checked against the engine.",
                       s.whatif_explain, after=0.6)],
          persona=PRIYA, start="/investor/what-if", ready="After 15 years",
          lower=("What-if Studio", "10,000 simulated futures · Gemini")),
    Scene("xray", [B("Lucas's X-ray looks through his funds to the companies underneath.", s.xray_look),
                   B("About a tenth of his money is NVIDIA, held through six different ETFs.", s.xray_nvda, after=0.6)],
          persona="lucas@atrium.demo", start="/investor/xray", ready="Things to look at",
          lower=("Portfolio X-ray", "Look-through to every company")),
    Scene("scenarios", [B("Scenario Studio replays the hardest markets since 2007 on what Priya holds.", s.scen_history),
                        B("Or she describes her own scenario, in plain English.", s.scen_type),
                        B("Gemini, grounded with Google Search, proposes the shocks; Atrium's engine prices them, and "
                          "she can change every one.", s.scen_map, after=0.6)],
          persona=PRIYA, start="/investor/scenarios", ready="2008 financial crisis",
          lower=("Scenario Studio", "Gemini · Google Search grounding")),
    Scene("copilot", [B("And the Investor Copilot, an agent built with ADK, answers in her own figures.", s.copilot_ask),
                      B("Here it asks the Pre-trade Guardian before she places anything.", s.copilot_read, after=0.6)],
          persona=PRIYA, start="/investor/copilot", ready="Try asking", lower=("Investor Copilot", "Agent Development Kit · Gemini")),

    shared("ch2"),
    shared("nvda"),
    shared("takeover"),
    shared("inbox"),

    shared("ch3"),
    shared("leads"),
    shared("identity"),
    shared("call"),
    Scene("proposal", [B("For a lead who fits, Gemini Pro writes a personalised proposal from the simulation and the "
                         "fund documents.", proposal_read),
                       B("Every figure is checked and every claim is cited. It is a draft for the advisor; nothing is "
                         "sent.", proposal_cited, after=0.6)],
          persona=DANIEL, start=f"/advisor/leads/{GRACE}", ready="Grace Holloway",
          lower=("Proposal", "Gemini Pro · Vertex AI Search · checked figures")),

    shared("ch4"),
    shared("alert"),
    shared("rings"),
    shared("models"),
    Scene("honest", [B("Every figure Gemini writes is checked against the engine that produced it, and every claim "
                       "cites its passage or its evidence row.", honest_log),
                     B("Every paragraph names the model that wrote it; agents propose and people decide anything that "
                       "moves money; and every call lands in the log with its cost.", honest_rows, after=0.8)],
          persona=OMAR, start="/compliance/log", ready="AI decisions", lower=("How the AI is kept honest", "Checked · cited · logged")),

    Scene("arch", [B("Under the hood, Cloud Run serves the app, the API and the nightly jobs. Gemini runs on Vertex "
                     "AI with ADK agents, beside Document AI, Vertex AI Search and BigQuery ML.", after=0.4),
                   B("Firebase Hosting and Auth are the front door, and Firestore streams every confirmation and "
                     "alert live.", after=0.9)],
          clip="arch"),
    Scene("next", [B("Next: a Gemini Live voice advisor, push alerts through Firebase Cloud Messaging, client "
                     "statements and tax reports straight from the ledger, and more funds and markets.", after=1.0)],
          clip="next"),
    shared("close"),
]

FRESH = [sc.key for sc in SCENES if sc.key not in SHARED]
