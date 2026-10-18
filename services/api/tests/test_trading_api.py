from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import select

from app.ai.llm import FakeLLM, get_llm
from app.markets.broker import PaperBroker, broker_dep
from app.markets.quotes import CommittedQuotes, quote_book
from app.models import AccountDevice, AIDecision, Person

DAILY = pd.DataFrame({"KO": [60.0, 61.0], "TSLA": [400.0, 400.0]}, index=pd.to_datetime(["2026-10-08", "2026-10-09"]))
HOLDER = {"X-Dev-User": "priya@example.test", "X-Device-Id": "browser-1",
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/141.0.0.0 Safari/537.36"}
ADVISOR = {"X-Dev-User": "daniel@atrium.demo"}
NARRATIVE = {"headline": "This order buys 3 shares of Coca-Cola for about $183.04.",
             "paragraphs": ["It should fill at about $61.01 a share."], "cautions": []}
REVIEW = {"summary": "The client asked to buy Tesla, which sits well above their risk profile.",
          "considerations": ["Tesla's price swings far more than the client's profile allows."],
          "questions_for_client": ["What is this money for, and when will you need it?"],
          "suggestion": "call_client", "suggestion_reason": "Confirm the client understands the extra risk."}


@pytest.fixture()
def api(client, db, account, people, paper):
    paper.deposit(account, "10000")
    db.get(Person, account.person_id).risk_band = 4
    db.commit()
    client.app.dependency_overrides[quote_book] = lambda: CommittedQuotes(DAILY)
    client.app.dependency_overrides[broker_dep] = PaperBroker
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({"order_explainer": NARRATIVE,
                                                                "held_order_review": REVIEW})
    return client


def orders(account):
    return f"/accounts/{account.id}/orders"


def test_preview_returns_the_guardians_report_and_remembers_the_browser(api, db, account):
    r = api.post(f"{orders(account)}/preview", headers=HOLDER, json={"symbol": "ko", "side": "buy", "quantity": 3})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == "proceed" and body["order"]["words"].startswith("Buy 3 shares of")
    assert {"PROFILE", "FUNDS", "SUITABILITY", "TRUST"} <= {c["code"] for c in body["checks"]}
    assert body["trust"]["signals"][0]["code"] == "T20" and body["estimate"]["value"] == "183.04"
    assert db.scalar(select(AccountDevice.label)) == "Chrome on Windows"


def test_explain_writes_a_checked_narrative(api, db, account):
    r = api.post(f"{orders(account)}/explain", headers=HOLDER, json={"symbol": "KO", "side": "buy", "quantity": 3})
    assert r.status_code == 200, r.text
    assert r.json()["narrative"]["verified"] is True and r.json()["report"]["verdict"] == "proceed"
    assert db.scalars(select(AIDecision.purpose)).all() == ["order_explainer"]


def test_place_list_and_cancel(api, account):
    placed = api.post(orders(account), headers=HOLDER, json={"symbol": "KO", "side": "buy", "quantity": 3})
    assert placed.status_code == 201, placed.text
    assert placed.json()["state"] == "filled" and placed.json()["name"]
    resting = api.post(orders(account), headers=HOLDER, json={"symbol": "KO", "side": "buy", "order_type": "limit",
                                                              "quantity": 10, "limit_price": "55"}).json()
    assert resting["state"] == "open"
    listed = api.get(orders(account), headers=HOLDER).json()
    assert [o["state"] for o in listed["orders"]] == ["open", "filled"]
    assert Decimal(listed["cash"]) == Decimal("9816.96") and Decimal(listed["cash_free"]) == Decimal("9266.96")
    assert api.post(f"{orders(account)}/{resting['id']}/cancel", headers=HOLDER).json()["state"] == "cancelled"
    assert api.post(f"{orders(account)}/{placed.json()['id']}/cancel", headers=HOLDER).status_code == 422


def test_a_held_order_goes_to_the_advisor_queue(api, db, account):
    db.get(Person, account.person_id).risk_band = 2
    db.commit()
    held = api.post(orders(account), headers=HOLDER, json={"symbol": "TSLA", "side": "buy", "quantity": 3}).json()
    assert (held["state"], held["verdict"]) == ("held", "hold")
    assert api.get("/orders/held", headers=HOLDER).status_code == 403
    queue = api.get("/orders/held", headers=ADVISOR).json()
    assert [o["id"] for o in queue] == [held["id"]] and queue[0]["client_name"] == "Priya Raman"
    noted = api.post(f"/orders/{held['id']}/review-note", headers=ADVISOR)
    assert noted.status_code == 200, noted.text
    assert noted.json()["ai_review"]["suggestion"] == "call_client" and noted.json()["ai_review"]["verified"] is True
    released = api.post(f"/orders/{held['id']}/release", headers=ADVISOR, json={"note": "Called the client."})
    assert released.json()["state"] == "filled" and released.json()["reviewed_by_name"] == "Daniel Okafor"
    assert api.post(f"/orders/{held['id']}/reject", headers=ADVISOR, json={}).status_code == 422
    assert api.post(f"/orders/{held['id']}/review-note", headers=ADVISOR).status_code == 409


def test_only_the_holder_places_orders_and_bad_orders_get_a_reason(api, account):
    assert api.post(orders(account), headers=ADVISOR, json={"symbol": "KO", "side": "buy",
                                                             "quantity": 1}).status_code == 403
    no_limit = api.post(f"{orders(account)}/preview", headers=HOLDER,
                        json={"symbol": "KO", "side": "buy", "order_type": "limit", "quantity": 1})
    assert no_limit.status_code == 422
    blocked = api.post(orders(account), headers=HOLDER, json={"symbol": "TSLA", "side": "buy", "quantity": 1000})
    assert blocked.status_code == 422 and "needs about" in blocked.json()["detail"]
    warned = api.post(orders(account), headers=HOLDER, json={"symbol": "TSLA", "side": "buy", "quantity": 1})
    assert warned.status_code == 422 and "confirm them" in warned.json()["detail"]


def test_a_staff_preview_does_not_record_the_advisors_browser_on_the_client(api, db, account):
    from sqlalchemy import func

    for path in ("preview", "explain"):
        r = api.post(f"{orders(account)}/{path}", headers={**ADVISOR, "X-Device-Id": "advisor-browser"},
                     json={"symbol": "KO", "side": "buy", "quantity": 1})
        assert r.status_code == 200, r.text
    assert db.scalar(select(func.count()).select_from(AccountDevice)) == 0


def test_a_held_order_tells_every_advisor_and_the_release_tells_the_holder(api, db, account, people, inbox):
    db.get(Person, account.person_id).risk_band = 2
    db.commit()
    held = api.post(orders(account), headers=HOLDER, json={"symbol": "TSLA", "side": "buy", "quantity": 3}).json()
    [notice] = inbox.to(people["advisor"])
    assert (notice.id, notice.stage, notice.severity, notice.href, notice.actor) == (
        f"order_held-{held['id']}", "trade", "attention", "/advisor/held", "Pre-trade Guardian")
    assert notice.title == "Priya Raman's purchase of 3 TSLA is held"
    assert notice.body == "Held for an advisor's review: suitability."
    assert inbox.to(account.person_id) == []
    released = api.post(f"/orders/{held['id']}/release", headers=ADVISOR, json={"note": "Called the client."}).json()
    [told] = inbox.to(account.person_id)
    assert (told.id, told.title, told.href, told.severity, told.actor) == (
        f"order_released-{held['id']}", "Daniel released your order", "/investor/trades", "info", "Daniel Okafor")
    price = f"${Decimal(released['fill_price']):,.2f}"
    assert told.body == f"Buy 3 TSLA at market. Filled at {price} a share. Daniel's note: Called the client."


def test_a_rejected_order_tells_the_holder_why(api, db, account, inbox):
    db.get(Person, account.person_id).risk_band = 2
    db.commit()
    held = api.post(orders(account), headers=HOLDER, json={"symbol": "TSLA", "side": "buy", "quantity": 3}).json()
    api.post(f"/orders/{held['id']}/reject", headers=ADVISOR, json={"note": "Too far outside your risk profile."})
    [told] = inbox.to(account.person_id)
    assert (told.id, told.severity) == (f"order_rejected-{held['id']}", "attention")
    assert told.title == "Daniel rejected your order: Too far outside your risk profile."
    assert told.body == "Buy 3 TSLA at market. Nothing was sent to the market."


def test_a_possible_takeover_is_urgent_for_the_advisors(api, db, account, people, paper, inbox):
    paper.trade(account, "buy", "TSLA", 20, 400)
    db.commit()
    held = api.post(orders(account), headers={**HOLDER, "X-Device-Id": "a-browser-never-seen"},
                    json={"symbol": "TSLA", "side": "sell", "quantity": 20}).json()
    assert (held["state"], held["guardian"]["takeover"]) == ("held", True)
    [notice] = inbox.to(people["advisor"])
    assert notice.severity == "urgent" and notice.title == "Priya Raman's sale of 20 TSLA is held"
    assert notice.body == ("Possible account takeover: a large sale from a device first seen within a day. "
                           f"Trust score {held['trust_score']} of 100.")
