"""The demo film, scene by scene: what the narrator says and what happens on screen, in the real app.

Each scene's `lines` are spoken in order; `act(r, t)` runs the scene, where t[i] is the second (on the scene's own
clock) that line i starts. Long Gemini waits are cut with a chip saying how long they really took. Scenes that
change data a judge will see later (accepting a match, approving with a code) run against a local copy of the app;
everything Gemini writes on screen comes from the live deployment.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

CARDS = Path(__file__).resolve().parent / "cards"
LIVE = "https://atrium-web-tvflgkcdoa-uc.a.run.app"
LOCAL = "http://localhost:3000"
RUTH = "be8280f2e7fe43a883ed789e8c91b9c0"
GEMINI_WAIT = "figure[role=status]"  # AiThinking, while Gemini works


@dataclass
class Scene:
    key: str
    lines: list[str]
    act: Callable[..., Awaitable[None]]
    persona: str | None = None
    start: str = "/"
    ready: str | None = None
    base: str = LIVE
    label: tuple[str, str, str] | None = None  # (number, stage, feature), shown for the scene's first seconds
    settle: float = 1.2
    tail: float = 0.9
    cursor: bool = True  # title cards have no pointer
    extra: dict = field(default_factory=dict)


# -- the acts --------------------------------------------------------------------------------------------------

async def open_card(r, t):
    await r.hold(t[-1] + 0.5)


async def front_door(r, t):
    await r.hold(2.2)
    await r.move_to(text="Start as Priya, an investor")
    await r.until(t[0] + 4.2)
    await r.move_to(text="Invest", sel="h3, h2, p, span, div", dx=60)


async def leads(r, t):
    await r.hold(1.2)
    await r.move_to(text="James Patel")
    await r.until(t[1] + 0.3)
    await r.move_to(text="Not an identity document")
    await r.hold(1.6)
    await r.move_to(text="Alex Mercer")
    await r.hold(0.8)
    await r.move_to(text="Many leads from one device")


async def call(r, t):
    await r.scroll_to(text="Gemini listens to a recorded call", at=0.22, ms=1100)
    await r.until(t[0] + 0.6)
    await r.click(text="Analyse the pressure call")
    await r.hold(2.4)
    await r.cut_wait(sel=GEMINI_WAIT, gone=True, timeout=150,
                     chip="Gemini listened to the 2½-minute call in {s} s · the wait is shortened")
    await r.scroll_by(260, 900)
    await r.until(t[1] + 0.4)
    await r.move_to(text="guarantees 8% a year", sel="p, li, span, blockquote, div")
    await r.until(t[2] + 0.2)
    await r.move_to(text="directing", sel="p, li, span, div")


async def rings(r, t):
    await r.hold(0.8)
    await r.scroll_to(text="How they connect", at=0.12, ms=1100)
    await r.until(t[1])
    await r.move_to(text="Sofia Rossi", sel="svg text, text")
    await r.hold(1.4)
    await r.click(text="Explain this ring")
    await r.cut_wait(sel=GEMINI_WAIT, gone=True, timeout=90, chip="Gemini read the ring in {s} s")
    await r.hold(0.8)
    await r.scroll_to(text="Point at a link id", at=0.1, ms=1100)  # the reading, under the graph
    await r.hold(1.0)


async def invest(r, t):
    await r.hold(1.4)
    await r.move_to(text="Your portfolio now")
    await r.until(t[1] - 0.6)
    await r.click(text="Portfolio", sel="aside a, nav a")
    await r.wait_for(text="Scenarios", sel="nav a")
    await r.click(text="Scenarios", sel="nav a")
    await r.wait_for(text="2008 financial crisis", timeout=60)
    await r.hold(1.6)
    await r.scroll_to(text="Your scenario", at=0.14, ms=1100)
    await r.click(sel="input[placeholder^='Oil at'], textarea[placeholder^='Oil at']")
    await r.type("Oil reaches $150 a barrel and the US enters a recession", per_char=0.03)
    await r.until(max(r.clock, t[2] - 0.2))
    await r.click(text="See what it could do")
    await r.hold(2.6)
    await r.cut_wait(sel=GEMINI_WAIT, gone=True, timeout=150,
                     chip="Gemini searched the news and proposed the shocks in {s} s · shortened")
    await r.scroll_by(320, 1000)
    await r.hold(1.2)


async def trade(r, t):
    await r.hold(0.8)
    await r.click(sel="input[inputmode=numeric]")
    await r.c.js("(() => { const i = document.querySelector('input[inputmode=numeric]'); i.select && i.select(); })()")
    await r.type("60", per_char=0.12)
    await r.until(t[0] + 2.4)
    await r.click(text="Check order")
    await r.hold(1.6)
    await r.cut_wait(sel=GEMINI_WAIT, gone=True, timeout=120, chip="The Guardian checked and Gemini explained in {s} s")
    await r.until(t[1])
    await r.move_to(text="Needs an advisor", sel="span, p, h2, h3, div")


async def operate(r, t):
    await r.hold(1.0)
    await r.move_to(text="Transactions read")
    await r.until(t[1] + 0.2)
    await r.scroll_to(text="Proposals to decide", at=0.12, ms=1100)
    await r.move_to(text="Gemini proposal")
    await r.hold(1.2)
    await r.move_to(text="Accept the match", exact=True)  # decided by a person; not clicked on the live demo


async def approve(r, t):
    # The second person: Sam approves a reversal Mei asked for, with a one-time code, on the local copy.
    code = await r.scene.extra["code"]()  # the authenticator code now, since codes change every 30 seconds
    await r.scroll_to(text="Code from your authenticator", at=0.45, ms=700)
    await r.click(sel="input[autocomplete='one-time-code'], input[inputmode=numeric]", pause_after=0.15)
    await r.type(code, per_char=0.1)
    await r.hold(0.3)
    await r.click(text="Approve", exact=True)
    await r.hold(1.3)


async def govern(r, t):
    await r.hold(1.2)
    await r.scroll_to(text="Inventory", at=0.15, ms=1100)
    await r.until(t[1] + 0.8)
    await r.click(text="Case review", sel="a, td, tr, div")
    await r.cut_wait(text="Golden cases", timeout=60)  # the model card loads off camera
    await r.hold(0.6)
    await r.until(t[2] - 0.4)
    await r.scroll_to(text="Red team", at=0.12, ms=1100)
    await r.hold(1.0)


async def close_card(r, t):
    await r.hold(t[-1] + 1.0)


SCENES: list[Scene] = [
    Scene("open", ["Wealth firms run on separate systems for leads, portfolios, trading and the books, and fraud slips "
                   "through the gaps."],
          open_card, start=(CARDS / "open.html").as_uri(), ready="Atrium", settle=0.0, tail=1.0, cursor=False),
    Scene("front", ["Atrium is one AI-native platform for the whole client life, from the first enquiry to a reconciled "
                    "ledger."],
          front_door, start="/", ready="A wealth firm run by", settle=0.0, tail=0.6),
    Scene("leads", ["Every lead is scored twice before an advisor calls: for fit, with BigQuery ML, and for trust.",
                    "The riskiest come first: a forged ID is blocked, and four leads from one device used throwaway "
                    "emails."],
          leads, persona="daniel@atrium.demo", start="/advisor", ready="Look at these first",
          label=("01", "Acquire", "Lead Score and Trust Score")),
    Scene("call", ["Gemini listens to recorded calls.",
                   "On Ruth's call, it hears a guaranteed eight percent a year, and a nephew directing her money.",
                   "Every flag quotes the transcript and the second it was said; anything it cannot ground is dropped."],
          call, persona="daniel@atrium.demo", start=f"/advisor/leads/{RUTH}", ready="Ruth Alvarez",
          label=("01", "Acquire", "Call intelligence")),
    Scene("rings", ["One identity graph runs across the whole lifecycle.",
                    "Those four leads share a device that also signs in to a client flagged for money in and straight "
                    "out.",
                    "Gemini explains the ring, citing only the graph's real links."],
          rings, persona="omar@atrium.demo", start="/compliance/rings", ready="The strongest ring",
          label=("01", "Acquire", "Fraud ring radar")),
    Scene("invest", ["Investors see risk drift before it hurts.",
                     "Scenario Studio replays the hardest markets since 2007 on what Priya holds, or takes her own "
                     "scenario in plain English.",
                     "Gemini, grounded with Google Search, proposes the shocks, and Atrium's engine prices them."],
          invest, persona="priya@atrium.demo", start="/investor", ready="Your portfolio", settle=0.2,
          label=("02", "Invest", "Risk and Scenario Studio")),
    Scene("trade", ["Before any order reaches the market, the Pre-trade Guardian checks suitability, concentration and "
                    "behaviour.",
                    "Sixty NVIDIA shares would take Priya past her risk profile, so it holds the order for an advisor, "
                    "and explains why."],
          trade, persona="priya@atrium.demo", start="/investor/markets/NVDA", ready="Check order",
          label=("03", "Trade", "Pre-trade Guardian")),
    Scene("operate", ["Operations get proposals, not chores.",
                      "Document AI reads the bank statement, an ADK agent proposes the matches rules can't make, and a "
                      "person decides each one."],
          operate, persona="mei@atrium.demo", start="/operations/reconciliation", ready="Proposals to decide",
          label=("04", "Operate", "Reconciliation"), tail=0.5),
    Scene("approve", ["Changing the books takes a second person and a one-time code, and every decision, human or "
                      "AI, lands in one log."],
          approve, persona="sam@atrium.demo", start="/operations/approvals", ready="Approve", base=LOCAL,
          label=("04", "Operate", "Two-person approval"), tail=0.4),
    Scene("govern", ["And every model is governed.",
                     "Golden tests gate each deploy; live checks, a red team and fair-lending tests then run against "
                     "Gemini itself.",
                     "When our red team steered a case review into closing an alert, its breaker paused it; a "
                     "tripwire now prevents it."],
          govern, persona="omar@atrium.demo", start="/compliance/models", ready="Inventory", settle=0.2,
          label=("05", "Govern", "Model Risk Office")),
    Scene("close", ["Atrium runs on Gemini, ADK, Document AI, Vertex AI Search and BigQuery, on Cloud Run.",
                    "People decide. The AI shows its working."],
          close_card, start=(CARDS / "close.html").as_uri(), ready="People decide.", settle=0.0, tail=1.2,
          cursor=False),
]
