"""The submission film: Atrium in under four minutes, told as one story. A visitor becomes a unit-trust holder,
the money is priced, allocated and reconciled, a trade is held, the lead pipeline and compliance watch.

Motion clips (tools/video/motion/clips) carry the opening, the chapter turns, the pooling drawing, the architecture
and the road ahead; everything between them is the live app, recorded beat by beat as in scenes.py. Each recorded
scene gets a motion label naming the feature and the Google technology behind it. The one action that changes data
a judge would see (publishing fund prices with a one-time code) runs on the local copy of the app.

    uv run --project services/api python tools/video/make_video.py --film film_short ...
"""
import asyncio
import json
import time
import urllib.request

import motion_clips
import scenes as s
from scenes import JAMES, LOCAL, RUTH, Beat as B, Scene, ai, hold

API = "https://atrium-api-tvflgkcdoa-uc.a.run.app"
LOCAL_API = "http://localhost:8000"
TOM_DEVICE = f"video-tom-{time.time():.0f}"  # a browser Tom's account has never seen, for every take

motion_clips.CHAPTERS = {  # the film's own chapters: unit trusts lead, as the team asked
    1: ("Unit trusts", "Seven funds, priced every evening, run from first look to a settled holding.",
        [("Priya Raman", "Investor"), ("Mei Tanaka", "Operations"), ("Sam Ortiz", "Operations")], "CHAPTER 01 OF 04"),
    2: ("Stocks", "Every order checked before it reaches the market, and held when it looks wrong.",
        [("Priya Raman", "Investor"), ("Tom Becker", "Investor"), ("Daniel Okafor", "Advisor")], "CHAPTER 02 OF 04"),
    3: ("Acquire", "Every lead scored for fit and for fraud before an advisor calls.",
        [("Daniel Okafor", "Advisor")], "CHAPTER 03 OF 04"),
    4: ("Protect and govern", "Financial crime caught with its evidence, and every model validated and watched.",
        [("Omar Haddad", "Compliance")], "CHAPTER 04 · ACROSS EVERY STAGE"),
}


def chapter(n: int) -> Scene:
    return Scene(f"ch{n}", [], clip=f"chapter{n}")


def _http(method: str, path: str, user: str, body: dict | None = None, device: str | None = None, base: str = API):
    headers = {"X-Dev-User": user, "Content-Type": "application/json"}
    if device:
        headers["X-Device-Id"] = device
    req = urllib.request.Request(f"{base}{path}", method=method, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read() or b"null")


# -- unit trusts -------------------------------------------------------------------------------------------------

async def analyzer_run(r):
    await s.analyzer_run(r)
    await r.move_to(text="Likely range")
    await r.hold(0.5)
    await r.move_to(text="Talk to an advisor about this plan")


async def funds_list(r):
    await r.hold(0.5)
    await r.move_to(text="Atrium Cash Reserve")
    await r.hold(0.4)
    await r.move_to(text="Atrium Technology")
    await r.hold(0.3)
    await r.click(text="Atrium Balanced")
    await r.wait_for(text="Growth of $10,000", timeout=30)
    await r.scroll_to(text="Growth of $10,000", at=0.15, ms=1000)
    await r.hold(0.5)
    await r.scroll_to(text="What it holds", at=0.15, ms=1000)


async def fund_fit(r):
    await r.scroll_to(text="Is it right for you?", at=0.15, ms=1000)
    await r.click(text="Ask Gemini whether it fits me")
    await ai(r, "Vertex AI Search and Gemini answered in {s} s", linger=1.6)
    await r.camera(text="Written by Gemini", sel="span, div, p, b, strong", zoom=1.14, ms=800)
    await r.hold(1.2)
    await r.camera_out(ms=700)


async def subscribe(r):
    await r.hold(0.3)
    await r.select("select", "ATR-BAL")
    await r.click(sel="input[inputmode=decimal]")
    await r.select_all("input[inputmode=decimal]")
    await r.type("500", per_char=0.12)
    await r.click(text="Review instruction")
    await r.wait_for(text="Place instruction", timeout=30)
    await r.hold(0.9)  # the checks against her profile and the minimum
    await r.click(text="Place instruction")
    await r.wait_for(sel="[data-inbox-toast]", timeout=45)
    r.cue("chime")
    await r.hold(0.5)
    await r.move_to(sel="[data-inbox-toast]")
    await r.hold(1.0)


async def price_mei(r):
    await r.hold(0.4)
    await r.scroll_to(text="Step log", sel="h2", at=0.15, ms=1000)
    await r.hold(0.5)
    await r.scroll_to(text="Draft prices", sel="h2", at=0.15, ms=1000)
    await r.hold(0.5)
    await r.click(sel="textarea")
    await r.type("Every move matches its ETFs' closes; no fund moved more than one percent.", per_char=0.025)
    await r.click(text="Ask for publication")
    await r.wait_for(text="Sent for approval", timeout=30)
    await r.hold(0.5)


async def publish_sam(r):
    await s.approve_code(r)


async def allocation(r):
    await r.goto("/operations", ready="Step log", settle=0.6)
    await r.scroll_to(text="Step log", sel="h2", at=0.12, ms=1000)
    await r.move_to(text="Allocation", sel="td, th, span, div, p")
    await r.hold(0.8)


async def watch_risk(r):
    await r.hold(0.4)
    await r.scroll_to(text="Where the risk comes from", at=0.12, ms=1000)
    await r.hold(0.6)
    await r.scroll_to(text="How your funds move together", at=0.15, ms=1000)


async def watch_orders(r):
    await r.goto("/investor/orders", ready="Review instruction", settle=0.6)
    await r.scroll_by(760, 1200)
    await r.hold(0.8)


# -- stocks ------------------------------------------------------------------------------------------------------

async def nvda_live(r):
    await r.hold(0.4)
    await r.move_to(text="Delayed price from Yahoo Finance", sel="span, p, div")


async def nvda_guardian(r):
    await s.nvda_check(r)
    await r.camera(text="Suitability", sel="span, p, div, h3, b, strong", zoom=1.14)
    await r.move_to(text="Suitability", sel="span, p, div, h3, b, strong")
    await r.hold(0.7)
    await r.camera_out()
    await r.move_to(text="Written by Gemini", sel="span, div, p, b, strong")
    await r.hold(0.5)


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
    await r.camera(text="Written by Gemini", sel="span, div, p, b, strong", zoom=1.12, ms=800)
    await r.hold(1.0)
    await r.camera_out(ms=700)
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


# -- the local copy ----------------------------------------------------------------------------------------------

def prepare_local() -> None:
    """The local copy must hold draft prices waiting to be published, and no other pending request, so Mei can
    ask and Sam can approve on camera."""
    pending = _http("GET", "/ops/approvals?state=pending", "sam@atrium.demo", base=LOCAL_API)
    if pending:  # Mei already asked: Sam's scene approves it
        print(f"  local copy: {len(pending)} request(s) waiting for Sam")
        return
    overview = _http("GET", "/ops/overview", "mei@atrium.demo", base=LOCAL_API)
    if not overview.get("drafts"):
        print("  local copy: running the day-end for draft prices")
        _http("POST", "/ops/day-end", "mei@atrium.demo", base=LOCAL_API)


# -- the film ----------------------------------------------------------------------------------------------------

DANIEL, PRIYA, OMAR, MEI, SAM = ("daniel@atrium.demo", "priya@atrium.demo", "omar@atrium.demo", "mei@atrium.demo",
                                 "sam@atrium.demo")

ANALYZER = (  # the public Return Analyzer: in the extended walkthrough, cut from the short film for time
    Scene("analyzer", [B("Anyone can start without signing in.", s.analyzer_open),
                       B("The Return Analyzer replays ten thousand futures from real market history since 2007, and "
                         "turns the plan into an application.", analyzer_run, after=0.4)],
          start="/", ready="See what your money could become",
          lower=("Return Analyzer", "10,000 futures · real prices since 2007"))
)

SCENES: list[Scene] = [
    Scene("hook", [B("Wealth firms run on separate systems: leads, portfolios, trading, and the books.", after=0.4),
                   B("Atrium is one AI-native wealth platform that follows a person from their first web form to a "
                     "settled, reconciled trade, and scores, explains and guards every step with Gemini.", after=0.5),
                   B("AI explains and proposes; engines count and decide; a person makes every decision that changes "
                     "money.", after=0.6)],
          clip="hook"),

    chapter(1),
    Scene("pool", [B("A unit trust pools many holders' money into one portfolio of low-cost ETFs.", after=0.2),
                   B("Every evening Atrium prices it, and each holder owns units of it.", after=0.5)],
          clip="pool"),
    Scene("fund", [B("Seven funds, from Cash Reserve to Technology, each explained from its fact sheet.", funds_list),
                   B("Gemini says whether Balanced fits Priya, citing the passages Vertex AI Search found.", fund_fit,
                     after=0.4)],
          persona=PRIYA, start="/investor/funds", ready="Funds",
          lower=("Unit trusts", "Fact sheets · Vertex AI Search · Gemini")),
    Scene("subscribe", [B("She puts five hundred dollars in. Atrium checks it against her risk band, accepts it for "
                          "the next published price, and her confirmation arrives at once, live through Firestore.",
                          subscribe, after=0.4)],
          persona=PRIYA, start="/investor/orders", ready="Review instruction",
          lower=("Fund order and confirmation", "Cloud Firestore · real time")),
    Scene("price", [B("Each evening the day-end prices every fund from its ETFs' closes.", price_mei, after=0.3)],
          persona=MEI, start="/operations", ready="Step log", base=LOCAL,
          lower=("Fund pricing", "Day-end job · Cloud Run")),
    Scene("publish", [B("Publishing takes a second person and a one-time code, so every order deals at an approved "
                        "price.", publish_sam, after=0.4)],
          persona=SAM, start="/operations/approvals", ready="Approve", base=LOCAL,
          lower=("Four-eyes publication", "One-time code")),
    Scene("allocate", [B("Document AI reads the bank statement, an ADK agent matches each payment to its order, and "
                         "a person accepts every match.", s.recon_propose, after=0.4)],
          persona=MEI, start="/operations/reconciliation", ready="Proposals to decide",
          lower=("Allocate and settle", "Document AI · ADK agent")),

    chapter(2),
    Scene("nvda", [B("The Pre-trade Guardian checks every order before it reaches the market: sixty NVIDIA shares "
                     "would take Priya two bands past her profile, so it is held, and Gemini explains why.",
                     nvda_guardian, after=0.4)],
          persona=PRIYA, start="/investor/markets/NVDA", ready="Check order",
          lower=("Pre-trade Guardian", "Rules engine · Gemini explains")),
    Scene("takeover", [B("Tom tries to sell his whole Tesla position from a browser his account has never seen.",
                         s.tom_sell, after=0.2),
                       B("The Guardian holds it as a possible account takeover.", s.tom_hold, after=0.4)],
          persona="tom@atrium.demo", start="/investor/markets/TSLA", ready="Check order",
          lower=("Account takeover", "Device trust signals"), extra={"device": TOM_DEVICE}),
    Scene("inbox", [B("And Daniel's inbox lights up at once, live through Firestore.", inbox_live, after=0.4),
                    B("Gemini Pro drafts the review note; Daniel makes the call.", held_note, after=0.5)],
          persona=DANIEL, start="/advisor", ready="Look at these first",
          lower=("Live inbox", "Cloud Firestore · real time")),

    chapter(3),
    Scene("leads", [B("Fraud starts at the lead. Every lead is scored twice, for fit with BigQuery ML and for trust "
                      "from the first form field, and four leads from one device go straight to the top.",
                      leads_triage, after=0.4)],
          persona=DANIEL, start="/advisor", ready="Look at these first", lower=("Lead triage", "BigQuery ML · Trust Score")),
    Scene("identity", [B("Document AI spots a manipulated ID, so James is blocked until a person checks.", james_block,
                         after=0.4)],
          persona=DANIEL, start=f"/advisor/leads/{JAMES}", ready="James Patel",
          lower=("Identity proofing", "Document AI")),
    Scene("call", [B("Gemini listens to Ruth's first call the way a compliance officer would.", ruth_call, after=0.3),
                   B("It flags a nephew directing her money and a promised eight percent, each flag quoting the second "
                     "it was said.", ruth_flags, after=0.5)],
          persona=DANIEL, start=f"/advisor/leads/{RUTH}", ready="Ruth Alvarez",
          lower=("Call intelligence", "Gemini audio understanding")),

    chapter(4),
    Scene("alert", [B("Seven AML scenarios and a BigQuery ML anomaly model catch structuring, just under ten thousand "
                      "dollars.", alert_open, after=0.3),
                    B("Gemini Pro reviews the case citing only its evidence, and the MLRO decides.", alert_review,
                      after=0.5)],
          persona=OMAR, start="/compliance", ready="Possible structuring",
          lower=("AML case review", "BigQuery ML · Gemini Pro")),
    Scene("rings", [B("One identity graph spans the whole lifecycle, and exposes a fraud ring reaching into a client's "
                      "account.", rings_flow, after=0.5)],
          persona=OMAR, start="/compliance/rings", ready="The strongest ring",
          lower=("Fraud ring radar", "One identity graph")),
    Scene("models", [B("The Model Risk Office gates every deploy with golden tests, attacks each model with a red "
                       "team, and logs every AI decision with its model and its cost.", models_flow, after=0.5)],
          persona=OMAR, start="/compliance/models", ready="Inventory", settle=0.4,
          lower=("Model Risk Office", "Golden tests · red team · decision log")),

    Scene("arch", [B("Under the hood, Cloud Run serves the app, the API and the nightly jobs; Gemini runs on Vertex "
                     "AI with ADK agents; and Firebase Hosting and Auth are the front door, with Firestore streaming "
                     "every confirmation and alert live.", after=0.5)],
          clip="arch"),
    Scene("close", [B("Atrium. People decide; the AI shows its working.", after=1.6)], clip="close"),
]
