"""Live smoke test of the Invest release against a deployed API, with the AI cost of the run.

Usage: python tools/smoke_invest.py [API_URL]
It uses the demo personas. It saves one risk profile for Hana Sato, a persona the demo script does not feature, and it
writes one proposal for a clear-trust lead. It places no instructions.
"""
import json
import sys
import time
import urllib.error
import urllib.request

API = sys.argv[1] if len(sys.argv) > 1 else "https://atrium-api-tvflgkcdoa-uc.a.run.app"
INVESTOR, ADVISOR = "hana@atrium.demo", "daniel@atrium.demo"


def call(method, path, body=None, user=INVESTOR, timeout=280):
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
    print(f"{label:<28} {status}  {seconds:5.1f}s  {detail}")
    return body if status in (200, 201) else None


def main():
    before = call("GET", "/ai/usage", user=ADVISOR)[1]
    account = call("GET", "/me")[1]["accounts"][0]["id"]
    plan = {"initial_usd": 25000, "monthly_usd": 500, "years": 15, "goal_usd": 250000,
            "scenarios": [{"allocation": {"ATR-BAL": 1}}, {"allocation": {"ATR-GRW": 1}}]}
    show("what-if", call("POST", "/invest/what-if", plan), lambda b: f"middle {b['scenarios'][0]['final']['p50']:,.0f}")
    show("what-if explained", call("POST", "/invest/what-if/explain", plan),
         lambda b: f"verified={b['narrative']['verified']} {b['narrative']['headline'][:70]}")
    show("risk", call("GET", f"/accounts/{account}/risk"),
         lambda b: f"band {b['portfolio_band']} vs profile {b['profile_band']} ({b['verdict']})")
    show("risk explained", call("POST", f"/accounts/{account}/risk/explain"), lambda b: f"verified={b['narrative']['verified']}")
    show("x-ray", call("GET", f"/accounts/{account}/xray"),
         lambda b: f"{len(b['warnings'])} warnings; largest company {b['companies'][0]['name']}")
    show("x-ray explained", call("POST", f"/accounts/{account}/xray/explain"), lambda b: f"verified={b['narrative']['verified']}")
    show("fund explainer", call("GET", "/funds/ATR-GLB/explainer"), lambda b: f"{len(b['sections'])} sections")
    show("fund fit", call("POST", "/funds/ATR-TEC/fit"),
         lambda b: f"retriever={b['retriever']} points={len(b['points'])} verdict={b['suitability']['verdict']}")
    first = show("profile chat 1", call("POST", "/me/risk-profile/chat", {"messages": [
        {"role": "user", "text": "About 20 years, and I won't need any of it before then. A 30% fall would be okay."}]}),
        lambda b: f"missing {b['missing']}")
    if first:
        second = show("profile chat 2", call("POST", "/me/risk-profile/chat", {"known": first["answers"], "messages": [
            {"role": "user", "text": "I'd hold and wait, and I have some experience."}]}),
            lambda b: f"complete={b['complete']} band={b['preview'] and b['preview']['band']}")
        if second and second["complete"]:
            show("profile saved", call("POST", "/me/risk-profile", {"answers": second["answers"], "source": "conversation"}),
                 lambda b: f"band {b['band']}")
    show("order preview", call("POST", f"/accounts/{account}/instructions/preview",
                               {"type": "subscribe", "fund_code": "ATR-TEC", "amount_usd": "1500"}),
         lambda b: f"ok={b['ok']} acknowledgement={b['needs_acknowledgement']}")
    show("copilot", call("POST", f"/accounts/{account}/copilot", {"question": "Why did my portfolio move over the last week?"}),
         lambda b: f"tools={[t['tool'] for t in b['trace']]} {b['answer'][:60]!r}")
    leads = call("GET", "/leads", user=ADVISOR)[1]
    lead = next(l for l in leads if l["trust_band"] == "clear" and l["stage"] != "client")
    show("proposal", call("POST", f"/leads/{lead['id']}/proposal", user=ADVISOR),
         lambda b: f"verified={b['verified']} compliance_ok={b['compliance']['ok']} retriever={b['content']['retriever']}")
    after = call("GET", "/ai/usage", user=ADVISOR)[1]
    print(f"\nAI spend this run: ${float(after['cost_usd']) - float(before['cost_usd']):.4f} "
          f"over {after['decisions'] - before['decisions']} logged decisions")
    for purpose, row in sorted(after["by_purpose"].items()):
        old = before["by_purpose"].get(purpose, {"count": 0, "cost_usd": "0"})
        if row["count"] > old["count"]:
            print(f"  {purpose:<22} {row['count'] - old['count']:>3} calls  ${float(row['cost_usd']) - float(old['cost_usd']):.4f}")


if __name__ == "__main__":
    main()
