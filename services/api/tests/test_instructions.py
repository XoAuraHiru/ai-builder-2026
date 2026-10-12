from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from app.models import Person
from app.seed.funds import seed_funds
from app.services.instructions import LotView, preview_redemption
from app.services.ledger import InsufficientUnits, apply_posting
from app.services.pricing import publish_prices

HDR = {"X-Dev-User": "priya@example.test"}


@pytest.fixture()
def holder(db, account):
    seed_funds(db)
    idx = pd.to_datetime(["2026-01-02", "2026-01-05"])
    for code in ("ATR-BAL", "ATR-GRW", "ATR-TEC", "ATR-CASH"):
        publish_prices(db, code, pd.Series([100.0, 110.0], index=idx), Decimal("1000000"))
    for day, price in [(date(2026, 1, 2), Decimal("100")), (date(2026, 1, 5), Decimal("110"))]:
        apply_posting(db, account_id=account.id, instrument="ATR-BAL", instrument_type="fund",
                      posting_type="subscription", units=Decimal("50"), cash=-50 * price, price=price, value_date=day,
                      reference="SUB")
    account.person.risk_band = 3
    db.commit()
    return account


def post(client, account, body, headers=HDR):
    return client.post(f"/accounts/{account.id}/instructions", json=body, headers=headers)


def test_redemption_preview_uses_fifo_lots():
    lots = [LotView(date(2026, 1, 2), Decimal("50"), Decimal("100")), LotView(date(2026, 1, 5), Decimal("50"), Decimal("110"))]
    p = preview_redemption("ATR-BAL", lots, Decimal("110"), date(2026, 1, 5), amount=Decimal("6600"))
    assert p.units == Decimal("60.000000") and p.value == Decimal("6600.00")
    assert p.cost == Decimal("6100.00") and p.realised_gain == Decimal("500.00")  # 50 x 100 + 10 x 110
    with pytest.raises(InsufficientUnits):
        preview_redemption("ATR-BAL", lots, Decimal("110"), date(2026, 1, 5), units=Decimal("101"))


def test_preview_lists_checks_and_needs_acknowledgement_above_band(client, holder):
    r = client.post(f"/accounts/{holder.id}/instructions/preview", headers=HDR,
                    json={"type": "subscribe", "fund_code": "ATR-TEC", "amount_usd": "2000"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["needs_acknowledgement"] is True
    assert "band 5" in body["suitability"] and body["estimate"]["units"] == "18.181818"


def test_subscription_above_band_requires_explicit_acknowledgement(client, holder):
    body = {"type": "subscribe", "fund_code": "ATR-TEC", "amount_usd": "2000"}
    r = post(client, holder, body)
    assert r.status_code == 409 and "Confirm" in r.json()["detail"]
    r = post(client, holder, {**body, "acknowledge_risk": True})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["state"] == "accepted" and out["acknowledged_risk"] is True
    assert [s["state"] for s in out["steps"]] == ["received", "checked", "accepted"]
    assert "acknowledged" in out["steps"][1]["note"]


def test_minimums_and_holdings_are_enforced(client, holder):
    small = post(client, holder, {"type": "subscribe", "fund_code": "ATR-BAL", "amount_usd": "100"})
    assert small.status_code == 409 and "at least" in small.json()["detail"]
    too_much = post(client, holder, {"type": "redeem", "fund_code": "ATR-BAL", "units": "500"})
    assert too_much.status_code == 409 and "hold" in too_much.json()["detail"]


def test_switch_records_both_funds_and_the_units_sold(client, holder):
    r = post(client, holder, {"type": "switch", "fund_code": "ATR-BAL", "to_fund_code": "ATR-CASH", "amount_usd": "1100"})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["to_fund_code"] == "ATR-CASH" and out["units"] == "10.000000" and out["amount"] is None
    assert out["to_fund_name"] == "Atrium Cash Reserve"
    listed = client.get(f"/accounts/{holder.id}/instructions", headers=HDR).json()
    assert listed[0]["id"] == out["id"]


def test_profile_is_required_before_instructions(client, db, holder):
    holder.person.risk_band = None
    db.commit()
    r = post(client, holder, {"type": "subscribe", "fund_code": "ATR-BAL", "amount_usd": "1000"})
    assert r.status_code == 409 and "risk profile" in r.json()["detail"]


def test_only_the_holder_can_instruct_but_staff_can_view(client, db, holder):
    db.add(Person(kind="advisor", full_name="Daniel Okafor", email="daniel@atrium.demo"))
    db.commit()
    staff = {"X-Dev-User": "daniel@atrium.demo"}
    assert post(client, holder, {"type": "subscribe", "fund_code": "ATR-BAL", "amount_usd": "1000"}, staff).status_code == 403
    assert client.get(f"/accounts/{holder.id}/instructions", headers=staff).status_code == 200


def test_bad_shapes_are_422(client, holder):
    assert post(client, holder, {"type": "redeem", "fund_code": "ATR-BAL", "amount_usd": "10", "units": "1"}).status_code == 422
    assert post(client, holder, {"type": "switch", "fund_code": "ATR-BAL", "to_fund_code": "ATR-BAL",
                                 "units": "1"}).status_code == 422
    assert post(client, holder, {"type": "subscribe", "fund_code": "NOPE", "amount_usd": "1000"}).status_code == 404


def test_monthly_plans_can_be_created_and_cancelled(client, holder):
    r = client.post(f"/accounts/{holder.id}/recurring", headers=HDR,
                    json={"fund_code": "ATR-BAL", "amount_usd": "250", "day_of_month": 5})
    assert r.status_code == 201, r.text
    plan = r.json()
    assert plan["status"] == "active" and plan["fund_name"] == "Atrium Balanced"
    above = client.post(f"/accounts/{holder.id}/recurring", headers=HDR,
                        json={"fund_code": "ATR-TEC", "amount_usd": "250", "day_of_month": 5})
    assert above.status_code == 409
    assert client.delete(f"/accounts/{holder.id}/recurring/{plan['id']}", headers=HDR).json()["status"] == "cancelled"
    assert [p["status"] for p in client.get(f"/accounts/{holder.id}/recurring", headers=HDR).json()] == ["cancelled"]
