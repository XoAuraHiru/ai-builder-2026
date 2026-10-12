"""Live smoke test of the Operate release against a deployed API, with the AI cost of the run.

Usage: python tools/smoke_operate.py [API_URL]

Persona sign-in only (the demo authenticator gives Sam's code). It does what a visitor would:
- Mei adds demo payments if fewer than three are waiting, reads the sample statement (a PDF through Document AI when
  the processor is configured), finds matches, and accepts the exact-reference ones.
- Mei runs the day-end and asks for any draft prices to be published; Sam approves with a one-time code.
- Omar opens the structuring alert and asks Gemini Pro for a case review. Nothing is decided, so the alerts stay open
  for visitors.
"""
import json
import sys
import time
import urllib.error
import urllib.request

API = sys.argv[1] if len(sys.argv) > 1 else "https://atrium-api-tvflgkcdoa-uc.a.run.app"
MEI, SAM, OMAR = "mei@atrium.demo", "sam@atrium.demo", "omar@atrium.demo"


def call(method, path, body=None, user=MEI, timeout=280):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(API + path, method=method, data=data,
                                 headers={"Content-Type": "application/json", "X-Dev-User": user})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null"), time.time() - started
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null"), time.time() - started


def show(label, result, describe):
    status, body, seconds = result
    detail = describe(body) if status in (200, 201) else body
    print(f"{label:<34} {status}  {seconds:5.1f}s  {detail}")
    return body if status in (200, 201) else None


def main():
    before = call("GET", "/ai/usage", user=OMAR)[1]
    view = show("reconciliation", call("GET", "/ops/reconciliation"),
                lambda b: f"{len(b['receipts'])} waiting, {len(b['unmatched'])} unmatched, PDF: {b['reads_pdf']}")
    if view and len([r for r in view["receipts"] if not r["in_proposal"]]) < 3:
        show("add demo payments", call("POST", "/ops/demo/payments"), lambda b: f"{b['added']} added")
    fmt = "pdf" if view and view["reads_pdf"] else "csv"
    show(f"read the sample statement ({fmt})", call("POST", "/ops/statements/sample", {"fmt": fmt}),
         lambda b: f"{b['source']}: {b['counts']}; {' '.join(b['notes'])[:80]}")
    show("find matches", call("POST", "/ops/reconcile"),
         lambda b: f"rules {b['rules']}, agent {b['agent']}, scorer {b['scorer']}: {b['summary'][:90]}")
    proposals = call("GET", "/ops/reconciliation")[1]["proposals"]
    for m in proposals:
        print(f"  proposal {m['tier']:<16} {m['confidence']:.2f}  by {m['proposed_by']:<7} "
              f"{', '.join(s['reference'] for s in m['subscriptions'])}  {m['evidence'][0][:70]}")
    for m in [m for m in proposals if m["tier"] == "exact_reference"]:
        show("accept an exact match", call("POST", f"/ops/matches/{m['id']}/accept", {}),
             lambda b: f"{b['state']} by {b['decided_by']}")
    run = show("day-end", call("POST", "/ops/day-end"),
               lambda b: f"{b['status']} for {b['as_of']}: " + "; ".join(f"{s['step']} {'ok' if s['ok'] else 'NO'}"
                                                                         for s in b["steps"]))
    if run and run["brief"]:
        print(f"  brief ({run['brief']['model']}, verified {run['brief']['verified']}): {run['brief']['headline']}")
    overview = call("GET", "/ops/overview")[1]
    if any(d["status"] == "draft" for d in overview["drafts"]):
        asked = show("ask to publish prices", call("POST", "/ops/prices/publish", {
            "as_of": overview["draft_as_of"], "reason": "Smoke test: every move matches its constituents."}),
            lambda b: b["summary"])
        if asked:
            code = call("GET", "/me/authenticator", user=SAM)[1]["code"]
            show("Sam approves with a code", call("POST", f"/ops/approvals/{asked['id']}/decide", {
                "approve": True, "code": code, "note": "Smoke test."}, user=SAM),
                lambda b: f"{b['state']}: {json.dumps(b['result'])[:90]}")
    alerts = show("open alerts", call("GET", "/compliance/alerts", user=OMAR),
                  lambda b: ", ".join(f"{a['title']} ({a['person']['name']})" for a in b))
    target = next((a for a in alerts or [] if a["scenario"] == "structuring"), None)
    if target:
        detail = call("GET", f"/compliance/alerts/{target['id']}", user=OMAR)[1]
        print(f"  graph: {len(detail['graph']['nodes'])} nodes, {len(detail['graph']['edges'])} links")
        show("case review (Gemini Pro)", call("POST", f"/compliance/alerts/{target['id']}/review", user=OMAR),
             lambda b: f"{b['ai_review']['triage']}, verified {b['ai_review']['verified']}: "
                       f"{b['ai_review']['narrative'][0]['text'][:80]}")
    after = call("GET", "/ai/usage", user=OMAR)[1]
    spent = float(after["cost_usd"]) - float(before["cost_usd"])
    print(f"\nAI cost of this run: ${spent:.4f} over {after['decisions'] - before['decisions']} AI decisions")
    for purpose, row in after["by_purpose"].items():
        was = before["by_purpose"].get(purpose, {"count": 0, "cost_usd": "0"})
        if row["count"] > was["count"]:
            print(f"  {purpose:<22} {row['count'] - was['count']} x  ${float(row['cost_usd']) - float(was['cost_usd']):.4f}")


if __name__ == "__main__":
    main()
