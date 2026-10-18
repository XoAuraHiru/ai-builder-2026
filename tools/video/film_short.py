"""The submission film: Atrium in under four minutes, the same real app as the full film, told tighter.

Motion clips (tools/video/motion/clips) carry the opening, the chapter turns, the architecture and the road ahead;
everything between them is the live app, recorded beat by beat as in scenes.py. Each recorded scene gets a motion
label naming the feature and the Google technology behind it, so a judge always knows what they are looking at.

    uv run --project services/api python tools/video/make_video.py --film film_short ...
"""
import asyncio
import json
import time
import urllib.request

import scenes as s
from scenes import JAMES, LOCAL, RUTH, Beat as B, Scene, ai, hold

API = "https://atrium-api-tvflgkcdoa-uc.a.run.app"
TOM_DEVICE = f"video-tom-{time.time():.0f}"  # a browser Tom's account has never seen, for every take


def chapter(n: int) -> Scene:
    return Scene(f"ch{n}", [], clip=f"chapter{n}")


# -- acquire -----------------------------------------------------------------------------------------------------

async def leads_triage(r):
    await r.hold(0.5)
    await r.move_to(text="Look at these first")
    await r.hold(0.5)
    await r.move_to(text="Many leads from one device")
    await r.hold(0.4)
    await r.move_to(text="Disposable email domain")


async def james_block(r):
    await r.scroll_to(text="Identity document", at=0.12, ms=1100)
    await r.move_to(text="Possible image manipulation")
    await r.hold(0.4)
    await r.move_to(text="Name does not match the form")


async def ruth_call(r):
    await r.scroll_to(text="Gemini listens to a recorded call", at=0.2, ms=1000)
    await r.click(text="Analyse the pressure call")
    await ai(r, "Gemini listened to the 2½-minute call in {s} s · the wait is shortened", linger=1.4)
    await r.scroll_by(300, 900)


async def ruth_flags(r):
    await r.camera(text="Third party directing the client", sel="span, div", zoom=1.16, ms=800)
    await r.move_to(text="Third party directing the client", sel="span, div")
    await r.hold(0.5)
    await r.move_to(text="Guarantee or promise", sel="span, div")
    await r.hold(0.3)
    await r.move_to(sel="button[aria-label*='Guarantee']")  # the play button: the second it was said
    await r.camera_out(ms=700)


# -- invest ------------------------------------------------------------------------------------------------------

async def home_drift(r):
    await r.hold(0.4)
    await r.move_to(text="Your profile", sel="span, div")
    await r.hold(0.5)
    await r.move_to(text="Your portfolio now", sel="span, div")


async def whatif_fan(r):
    await r.hold(0.6)
    await r.move_to(text="After 15 years", sel="h2")


async def xray_nvda(r):
    await r.hold(0.4)
    await r.move_to(text="Three companies are each a large share")
    await r.hold(0.4)
    await r.scroll_to(text="Largest companies you own", at=0.15, ms=1100)
    await r.move_to(text="NVIDIA Corp")


async def scen_type(r):
    await r.scroll_to(text="Your scenario", sel="h2", at=0.14, ms=1000)
    await r.click(sel="input[placeholder^='Oil at'], textarea[placeholder^='Oil at']")
    await r.type("Oil reaches $150 a barrel and the US enters a recession", per_char=0.03)


async def scen_map(r):
    await r.click(text="See what it could do")
    await ai(r, "Gemini searched the news and proposed the shocks in {s} s · shortened", linger=1.6)
    await r.scroll_to(text="The shocks", sel="h2", at=0.12, ms=1100)
    await r.move_to(text="Energy", sel="span, div, p")


async def copilot_ask(r):
    await r.hold(0.3)
    await r.click(text="What would the Guardian say if I bought 10 shares of NVIDIA?")
    await ai(r, "The Copilot agent answered in {s} s", linger=1.4, timeout=150)
    await r.scroll_by(220, 1100)


# -- trade -------------------------------------------------------------------------------------------------------

async def nvda_hold(r):
    await r.camera(text="Suitability", sel="span, p, div, h3, b, strong", zoom=1.14)
    await r.move_to(text="Suitability", sel="span, p, div, h3, b, strong")
    await r.hold(0.8)
    await r.camera_out()


def _http(method: str, path: str, user: str, body: dict | None = None, device: str | None = None):
    headers = {"X-Dev-User": user, "Content-Type": "application/json"}
    if device:
        headers["X-Device-Id"] = device
    req = urllib.request.Request(f"{API}{path}", method=method, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read() or b"null")


def tom_places_order() -> dict:
    """Tom, from the unseen browser, sends his whole Tesla position to market: the Guardian holds it."""
    account = _http("GET", "/me", "tom@atrium.demo", device=TOM_DEVICE)["accounts"][0]
    return _http("POST", f"/accounts/{account['id']}/orders", "tom@atrium.demo", device=TOM_DEVICE,
                 body={"symbol": "TSLA", "side": "sell", "order_type": "market", "quantity": 120,
                       "acknowledge_warnings": False})


async def inbox_live(r):
    """On Daniel's screen: Tom's order is placed elsewhere, and the inbox toast arrives through Firestore."""
    await r.hold(0.6)
    asyncio.get_running_loop().run_in_executor(None, tom_places_order)
    await r.wait_for(sel="[data-inbox-toast]", timeout=45)
    r.cue("chime")
    await r.hold(0.4)
    await r.move_to(sel="[data-inbox-toast]")
    await r.hold(0.8)
    await r.click(sel="[data-inbox-toast]")
    await r.wait_for(text="Held orders", timeout=30)


async def held_note(r):
    # The queue opens its oldest order; Tom's, just held, is the newest, at the bottom.
    newest = await r.c.js("""(() => { const all = [...document.querySelectorAll('button')]
      .filter((b) => b.innerText.trim() === 'Review this order'); const last = all[all.length - 1];
      if (last) last.setAttribute('data-video-target', 'newest'); return all.length; })()""")
    if newest:
        await r.scroll_to(sel="[data-video-target=newest]", at=0.3, ms=1000)
        await r.click(sel="[data-video-target=newest]")
        await r.hold(0.5)
    await r.scroll_to(text="Review note", sel="h2", at=0.15, ms=1100)
    await r.click(text="Ask Gemini Pro for a review note")
    await ai(r, "Gemini Pro wrote the note in {s} s · the wait is shortened", linger=1.8)
    await r.move_to(text="Release the order")


# -- operate -----------------------------------------------------------------------------------------------------

async def recon_flow(r):
    await r.hold(0.5)
    await r.move_to(text="Transactions read")
    await r.hold(0.4)
    await r.scroll_to(text="Proposals to decide", at=0.12, ms=1100)
    await r.move_to(text="Proposed by the reconciliation agent")
    await r.hold(0.5)
    await r.move_to(text="Accept the match", exact=True)  # decided by a person; not clicked on the live demo


async def approve_code(r):
    code = await r.scene.extra["code"]()  # the authenticator code now, since codes change every 30 seconds
    await r.scroll_to(text="Code from your authenticator", at=0.45, ms=800)
    await r.click(sel="input[autocomplete='one-time-code'], input[inputmode=numeric]", pause_after=0.15)
    await r.type(code, per_char=0.09)
    await r.hold(0.25)
    await r.click(text="Approve", exact=True)
    await r.hold(0.9)


# -- protect and govern ------------------------------------------------------------------------------------------

async def alert_open(r):
    await r.hold(0.4)
    await r.click(text="Possible structuring", sel="a")
    await r.cut_wait(text="Case review", timeout=60)
    await r.camera(text="reporting threshold", sel="span, div, text, p", zoom=1.12)
    await r.move_to(text="reporting threshold", sel="span, div, text, p")
    await r.hold(0.6)
    await r.camera_out()


async def alert_review(r):
    await r.scroll_to(text="Case review", sel="h2", at=0.1, ms=1100)
    await r.hold(0.8)
    await r.move_to(text="Escalate", exact=True)


async def rings_flow(r):
    await r.hold(0.4)
    await r.scroll_to(text="How they connect", at=0.12, ms=1100)
    await r.move_to(text="Sofia Rossi", sel="svg text, text")


async def models_flow(r):
    await r.hold(0.4)
    await r.click(text="Case review", sel="a, td, tr, div")
    await r.cut_wait(text="Golden cases", timeout=60)
    await r.hold(0.4)
    await r.scroll_to(text="Red team", at=0.12, ms=1200)
    await r.hold(0.6)
    await r.goto("/compliance/log", ready="AI decisions", settle=0.6)
    await r.scroll_to(text="AI decisions", sel="h2", at=0.15, ms=1000)


# -- the film ----------------------------------------------------------------------------------------------------

DANIEL, PRIYA, OMAR = "daniel@atrium.demo", "priya@atrium.demo", "omar@atrium.demo"

SCENES: list[Scene] = [
    Scene("hook", [B("Wealth firms run on four separate systems: leads, portfolios, trading, and the books.", after=0.5),
                   B("Fraud slips through the gaps between them, and the AI bolted on top is a black box.", after=0.7),
                   B("Atrium is one AI-native platform for the whole client life, with Gemini at every step, and a "
                     "person making every decision.", after=1.1)],
          clip="hook"),

    chapter(1),
    Scene("leads", [B("Every lead is scored twice: for fit, with BigQuery ML, and for trust. Four leads from one device "
                      "in a day go straight to the top.", leads_triage, after=0.6)],
          persona=DANIEL, start="/advisor", ready="Look at these first", lower=("Lead triage", "BigQuery ML · Trust Score")),
    Scene("identity", [B("Document AI spots a manipulated ID, so James is blocked until a person checks.", james_block,
                         after=0.7)],
          persona=DANIEL, start=f"/advisor/leads/{JAMES}", ready="James Patel",
          lower=("Identity proofing", "Document AI")),
    Scene("call", [B("Gemini listens to Ruth's first call the way a compliance officer would.", ruth_call, after=0.3),
                   B("It flags a nephew directing her money and a promised eight percent, each flag quoting the second "
                     "it was said.", ruth_flags, after=0.8)],
          persona=DANIEL, start=f"/advisor/leads/{RUTH}", ready="Ruth Alvarez",
          lower=("Call intelligence", "Gemini audio understanding")),

    chapter(2),
    Scene("whatif", [B("What-if Studio replays ten thousand futures from real markets.", whatif_fan, after=0.2),
                     B("Gemini explains the range, and every figure it writes is checked against the engine.",
                       s.whatif_explain, after=0.9)],
          persona=PRIYA, start="/investor/what-if", ready="After 15 years",
          lower=("What-if Studio", "10,000 simulated futures · Gemini")),
    Scene("scenarios", [B("Scenario Studio turns plain English into market shocks.", scen_type, after=0.2),
                        B("Gemini proposes them, grounded with Google Search, and Atrium's engine prices each one.",
                          scen_map, after=0.8)],
          persona=PRIYA, start="/investor/scenarios", ready="2008 financial crisis",
          lower=("Scenario Studio", "Gemini · Google Search grounding")),
    Scene("copilot", [B("And the Investor Copilot, an ADK agent, answers in her own numbers.", copilot_ask, after=0.8)],
          persona=PRIYA, start="/investor/copilot", ready="Try asking",
          lower=("Investor Copilot", "Agent Development Kit · Gemini")),

    chapter(3),
    Scene("nvda", [B("Before any order reaches the market, the Pre-trade Guardian checks it.", s.nvda_check, after=0.2),
                   B("Sixty NVIDIA shares would take Priya two bands past her profile, so it's held for an advisor.",
                     nvda_hold, after=0.8)],
          persona=PRIYA, start="/investor/markets/NVDA", ready="Check order",
          lower=("Pre-trade Guardian", "Rules engine · Gemini explains")),
    Scene("takeover", [B("Tom tries to sell his whole Tesla position from a browser his account has never seen.",
                         s.tom_sell, after=0.2),
                       B("The Guardian holds it as a possible account takeover.", s.tom_hold, after=0.6)],
          persona="tom@atrium.demo", start="/investor/markets/TSLA", ready="Check order",
          lower=("Account takeover", "Device trust signals"), extra={"device": TOM_DEVICE}),
    Scene("inbox", [B("And Daniel's inbox lights up at once, live through Firestore.", inbox_live, after=0.4),
                    B("Gemini Pro drafts the review note; Daniel makes the call.", held_note, after=0.9)],
          persona=DANIEL, start="/advisor", ready="Look at these first",
          lower=("Live inbox", "Cloud Firestore · real time")),

    chapter(4),
    Scene("recon", [B("Each evening a Cloud Run job closes the day. Document AI reads the bank statement, and an ADK "
                      "agent proposes the matches rules can't make.", recon_flow, after=0.8)],
          persona="mei@atrium.demo", start="/operations/reconciliation", ready="Proposals to decide",
          lower=("Reconciliation", "Document AI · ADK agent")),
    Scene("approve", [B("Changing the books takes a second person and a one-time code.", approve_code, after=0.7)],
          persona="sam@atrium.demo", start="/operations/approvals", ready="Approve", base=LOCAL,
          lower=("Four-eyes approval", "One-time code")),

    chapter(5),
    Scene("alert", [B("Seven AML scenarios and a BigQuery ML anomaly model catch structuring, just under ten thousand "
                      "dollars.", alert_open, after=0.3),
                    B("Gemini Pro reviews the case, citing only its evidence, and a person decides.", alert_review,
                      after=0.8)],
          persona=OMAR, start="/compliance", ready="Possible structuring",
          lower=("AML case review", "BigQuery ML · Gemini Pro")),
    Scene("rings", [B("One identity graph spans the whole lifecycle, and exposes a fraud ring reaching into a client's "
                      "account.", rings_flow, after=0.8)],
          persona=OMAR, start="/compliance/rings", ready="The strongest ring",
          lower=("Fraud ring radar", "One identity graph")),
    Scene("models", [B("The Model Risk Office gates every deploy with golden tests, attacks each model with a red-team "
                       "agent, and logs every AI decision with its cost.", models_flow, after=0.8)],
          persona=OMAR, start="/compliance/models", ready="Inventory", settle=0.4,
          lower=("Model Risk Office", "Golden tests · red team · decision log")),

    Scene("arch", [B("Under the hood, Cloud Run serves the app, the API and the nightly jobs. Gemini runs on Vertex AI, "
                     "with ADK agents.", after=0.4),
                   B("Firebase Hosting and Auth are the front door, and Firestore streams the live inbox.", after=0.9)],
          clip="arch"),
    Scene("next", [B("Next: a Gemini Live voice advisor, push alerts through Firebase Cloud Messaging, fraud signals "
                     "shared across firms in BigQuery clean rooms, and agents that keep every KYC file current.",
                     after=1.0)],
          clip="next"),
    Scene("close", [B("Atrium. People decide; the AI shows its working.", after=2.2)], clip="close"),
]
