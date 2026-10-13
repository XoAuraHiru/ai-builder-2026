"""Live smoke test of the Trade release against a deployed API, with the AI cost of the run.

Usage: python tools/smoke_trade.py [API_URL]
It uses the demo personas from a browser Atrium has never seen. Previews place nothing. It places two small orders:
Tom buys one Coca-Cola share (filled), and Noah's one-share Tesla order is held, given a review note and rejected.
"""
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

API = sys.argv[1] if len(sys.argv) > 1 else "https://atrium-api-tvflgkcdoa-uc.a.run.app"
ADVISOR = "daniel@atrium.demo"
# One new device per persona and run: a device shared by several investors is what the fraud ring radar looks for.
RUN = uuid.uuid4().hex[:12]


def call(method, path, body=None, user="tom@atrium.demo", timeout=280):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(API + path, method=method, data=data, headers={
        "Content-Type": "application/json", "X-Dev-User": user, "X-Device-Id": f"smoke-{RUN}-{user}"})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null"), time.time() - started
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null"), time.time() - started


def show(label, result, describe):
    status, body, seconds = result
    detail = describe(body) if status in (200, 201) else body
    print(f"{label:<32} {status}  {seconds:5.1f}s  {detail}")
    return body if status in (200, 201) else None


def verdict(b):
    concerns = [c["title"] for c in b["checks"] if c["outcome"] in ("warn", "hold", "block")]
    return f"{b['verdict']}: {', '.join(concerns) or 'no concerns'}; trust {b['trust']['score']}"


def main():
    before = call("GET", "/ai/usage", user=ADVISOR)[1]
    show("markets", call("GET", "/markets"),
         lambda b: f"{len(b['rows'])} symbols, source {b['rows'][0]['source']}; {b['session']['label']}")
    show("NVDA page", call("GET", "/markets/NVDA"),
         lambda b: f"${float(b['quote']['price']):,.2f}, band {b['risk_band']}, {len(b['history'])} days of closes")
    ids = {p: call("GET", "/me", user=f"{p}@atrium.demo")[1]["accounts"][0]["id"]
           for p in ("priya", "lucas", "tom", "hana", "noah")}

    def preview(person, symbol, side, quantity):
        return call("POST", f"/accounts/{ids[person]}/orders/preview",
                    {"symbol": symbol, "side": side, "quantity": quantity}, user=f"{person}@atrium.demo")

    show("Priya buys 60 NVDA", preview("priya", "NVDA", "buy", 60), verdict)
    show("Lucas buys 30 NVDA", preview("lucas", "NVDA", "buy", 30), verdict)
    show("Tom sells 120 TSLA, new device", preview("tom", "TSLA", "sell", 120), verdict)
    sold = [o for o in call("GET", f"/accounts/{ids['hana']}/orders", user="hana@atrium.demo")[1]["orders"]
            if o["side"] == "sell"]
    if sold:
        show(f"Hana buys back {sold[0]['symbol']}", preview("hana", sold[0]["symbol"], "buy", 10), verdict)
    show("explained (Gemini Flash)", call("POST", f"/accounts/{ids['priya']}/orders/explain",
                                          {"symbol": "NVDA", "side": "buy", "quantity": 60}, user="priya@atrium.demo"),
         lambda b: f"verified={b['narrative']['verified']} {b['narrative']['headline'][:70]}")
    show("Tom buys 1 KO", call("POST", f"/accounts/{ids['tom']}/orders", {"symbol": "KO", "side": "buy", "quantity": 1}),
         lambda b: f"{b['state']} at {b['fill_price']}")
    held = show("Noah buys 1 TSLA", call("POST", f"/accounts/{ids['noah']}/orders",
                                         {"symbol": "TSLA", "side": "buy", "quantity": 1}, user="noah@atrium.demo"),
                lambda b: f"{b['state']} ({b['verdict']})")
    if held and held["state"] == "held":
        show("review note (Gemini Pro)", call("POST", f"/orders/{held['id']}/review-note", user=ADVISOR),
             lambda b: f"verified={b['ai_review']['verified']} suggests {b['ai_review']['suggestion']}")
        show("advisor rejects", call("POST", f"/orders/{held['id']}/reject",
                                     {"note": "Smoke test of the advisor queue."}, user=ADVISOR), lambda b: b["state"])
    show("held queue", call("GET", "/orders/held", user=ADVISOR), lambda b: f"{len(b)} waiting")
    after = call("GET", "/ai/usage", user=ADVISOR)[1]
    print(f"\nAI spend this run: ${float(after['cost_usd']) - float(before['cost_usd']):.4f} "
          f"over {after['decisions'] - before['decisions']} logged decisions")
    for purpose, row in sorted(after["by_purpose"].items()):
        old = before["by_purpose"].get(purpose, {"count": 0, "cost_usd": "0"})
        if row["count"] > old["count"]:
            print(f"  {purpose:<22} {row['count'] - old['count']:>3} calls  ${float(row['cost_usd']) - float(old['cost_usd']):.4f}")


if __name__ == "__main__":
    main()
