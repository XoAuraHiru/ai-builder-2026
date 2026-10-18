from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd
import pyotp
import pytest
from sqlalchemy import select

from app.ai.llm import FakeLLM, get_llm
from app.config import get_settings
from app.models import Account, AmlAlert, Fund, Instruction, Price
from app.seed.funds import all_tickers, seed_funds
from app.services.fund_pricing import draft_prices
from app.services.instructions import payment_reference
from app.services.pricing import publish_prices

PREV, AS_OF = date(2026, 10, 8), date(2026, 10, 9)
MEI, SAM, OMAR = ({"X-Dev-User": f"{who}@atrium.demo"} for who in ("mei", "sam", "omar"))
INVESTOR = {"X-Dev-User": "priya@example.test"}
REVIEW = {"triage": "escalate", "triage_reason": "Three payments sit just under the reporting threshold.",
          "narrative": [{"text": "Priya Raman subscribed $9,400.00 on October 6.", "evidence": ["i1"]}],
          "questions": ["Where did the money come from?"]}


def code(person) -> str:
    return pyotp.TOTP(person.totp_secret).now()


def wrong_code(person) -> str:
    totp, now = pyotp.TOTP(person.totp_secret), datetime.now(timezone.utc)
    valid = {totp.at(now + timedelta(seconds=s)) for s in (-30, 0, 30)}
    return next(c for c in ("000000", "111111", "222222", "333333") if c not in valid)


@pytest.fixture()
def api(client, db, staff, account):
    seed_funds(db)
    for fund_code in db.scalars(select(Fund.code)).all():
        publish_prices(db, fund_code, pd.Series([100.0], index=pd.to_datetime([PREV])), Decimal("1000"))
    db.add(Instruction(account_id=account.id, fund_code="ATR-BAL", type="subscribe", amount=Decimal("1500"),
                       state="accepted", requested_at=datetime(2026, 10, 9, 14, tzinfo=timezone.utc)))
    closes = pd.DataFrame({t: [100.0, 101.0] for t in all_tickers()}, index=pd.to_datetime([PREV, AS_OF]))
    draft_prices(db, AS_OF, closes)
    db.commit()
    return client


def test_each_workspace_is_for_its_own_staff(api):
    assert api.get("/ops/overview", headers=INVESTOR).status_code == 403
    assert api.get("/ops/overview", headers=OMAR).status_code == 403
    assert api.get("/compliance/alerts", headers=MEI).status_code == 403
    assert api.get("/ops/overview", headers=MEI).status_code == 200
    assert api.get("/compliance/alerts", headers=OMAR).status_code == 200


def test_prices_are_published_by_a_second_person_with_a_code(api, db, staff):
    overview = api.get("/ops/overview", headers=MEI).json()
    assert overview["draft_as_of"] == "2026-10-09" and len(overview["drafts"]) == 7
    assert Decimal(overview["drafts"][0]["nav"]) > Decimal("100") and overview["waiting_for_money"] == 1
    asked = api.post("/ops/prices/publish", headers=MEI,
                     json={"as_of": "2026-10-09", "reason": "Checked against the closes."})
    assert asked.status_code == 201, asked.text
    approval = asked.json()
    assert approval["state"] == "pending" and approval["mine"] is True and approval["requested_by"] == "Mei Tanaka"
    path = f"/ops/approvals/{approval['id']}/decide"
    own = api.post(path, headers=MEI, json={"approve": True, "code": code(staff["mei"])})
    assert own.status_code == 422 and "different person" in own.json()["detail"]
    wrong = api.post(path, headers=SAM, json={"approve": True, "code": wrong_code(staff["sam"])})
    assert wrong.status_code == 422 and "code" in wrong.json()["detail"]
    done = api.post(path, headers=SAM, json={"approve": True, "code": code(staff["sam"]), "note": "Matches the closes."})
    assert done.status_code == 200, done.text
    assert done.json()["state"] == "approved" and done.json()["result"]["published"] == 7
    assert db.scalar(select(Instruction.state)) == "allocated"
    assert {p.status for p in db.scalars(select(Price).where(Price.as_of == AS_OF)).all()} == {"published"}
    assert api.get("/ops/approvals?state=pending", headers=SAM).json() == []


def test_a_statement_is_read_reconciled_and_accepted(api, db):
    reference = payment_reference(db.scalar(select(Instruction.id)))
    data = (f"Date,Description,Amount\n2026-10-09,ACH CREDIT PRIYA RAMAN REF {reference},1500.00\n"
            "2026-10-09,MONTHLY SERVICE FEE,-15.00\n").encode()
    uploaded = api.post("/ops/statements", headers=MEI, files={"file": ("october.csv", data, "text/csv")})
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["counts"]["unmatched"] == 1 and uploaded.json()["uploaded_by"] == "Mei Tanaka"
    again = api.post("/ops/statements", headers=MEI, files={"file": ("copy.csv", data, "text/csv")})
    assert again.status_code == 422 and "already been uploaded" in again.json()["detail"]
    found = api.post("/ops/reconcile", headers=MEI)
    assert found.status_code == 200 and found.json()["rules"] == 1
    proposal = api.get("/ops/reconciliation", headers=MEI).json()["proposals"][0]
    assert proposal["tier"] == "exact_reference" and proposal["subscriptions"][0]["reference"] == reference
    assert proposal["lines"][0]["amount"] == "1500.00" and proposal["evidence"]
    accepted = api.post(f"/ops/matches/{proposal['id']}/accept", headers=SAM, json={})
    assert accepted.status_code == 200 and accepted.json()["state"] == "accepted"
    after = api.get("/ops/reconciliation", headers=MEI).json()
    assert after["unmatched"] == [] and after["receipts"] == [] and after["recent"][0]["decided_by"] == "Sam Ortiz"
    assert after["reads_pdf"] is False  # no Document AI processor in tests
    again = api.post(f"/ops/matches/{proposal['id']}/reject", headers=SAM, json={"note": "Too late."})
    assert again.status_code == 422


def test_the_sample_statement_downloads_and_reads_straight_in(api):
    pdf = api.get("/ops/statements/sample?fmt=pdf", headers=MEI)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["content-type"] == "application/pdf"
    unread = api.post("/ops/statements/sample", headers=MEI, json={"fmt": "pdf"})
    assert unread.status_code == 422 and "CSV" in unread.json()["detail"]  # no Document AI in tests
    read = api.post("/ops/statements/sample", headers=MEI, json={"fmt": "csv"})
    assert read.status_code == 201, read.text
    assert read.json()["counts"]["unmatched"] >= 2 and read.json()["lines"]


def test_the_sample_statement_is_read_as_csv_unless_settings_ask_for_pdf(api, monkeypatch):
    view = api.get("/ops/reconciliation", headers=MEI).json()
    assert view["sample_format"] == "csv"  # a PDF read costs $0.75 of Document AI, so the sample is CSV by default
    read = api.post("/ops/statements/sample", headers=MEI, json={})
    assert read.status_code == 201, read.text
    assert read.json()["source"] == "csv"
    monkeypatch.setattr(get_settings(), "sample_statement_format", "pdf")
    view = api.get("/ops/reconciliation", headers=MEI).json()
    assert view["sample_format"] == "csv"  # asked for PDF, but no Document AI here to read it


def test_a_manual_match_and_the_blotter(api, db):
    data = b"Date,Description,Amount\n2026-10-09,CHECK DEPOSIT 4471,1500.00\n"
    statement = api.post("/ops/statements", headers=MEI, files={"file": ("check.csv", data, "text/csv")}).json()
    line_id = api.get(f"/ops/statements/{statement['id']}", headers=MEI).json()["lines"][0]["id"]
    instruction_id = db.scalar(select(Instruction.id))
    asked = api.post("/ops/matches/manual", headers=MEI, json={
        "line_ids": [line_id], "instruction_ids": [instruction_id], "reason": "The client sent a check."})
    assert asked.status_code == 201, asked.text
    assert asked.json()["action"] == "manual_match"
    waiting = api.get("/ops/reconciliation", headers=MEI).json()["proposals"]
    assert [m["state"] for m in waiting] == ["awaiting_approval"]
    row = api.get("/ops/blotter", headers=MEI).json()[0]
    assert row["reference"] == payment_reference(instruction_id) and row["funded"] is False
    assert row["steps"] == [] and row["posting_id"] is None
    assert api.post("/ops/reversals", headers=MEI, json={"posting_id": "nope", "reason": "x"}).status_code == 422


def test_a_settled_subscription_is_paid_even_without_a_statement_match(api, db, account):
    db.add(Instruction(account_id=account.id, fund_code="ATR-BAL", type="subscribe", amount=Decimal("900"),
                       state="settled", requested_at=datetime(2026, 9, 2, 14, tzinfo=timezone.utc)))
    db.commit()
    rows = {r["state"]: r for r in api.get("/ops/blotter", headers=MEI).json()}
    assert rows["settled"]["funded"] is True and rows["accepted"]["funded"] is False


def test_the_persona_demo_can_add_payments_to_wait_for(api, db, people, monkeypatch):
    db.add(Account(person_id=people["investor"].id, number="ACC-0002", opened_on=date(2026, 1, 5)))
    db.commit()
    added = api.post("/ops/demo/payments", headers=MEI)
    assert added.status_code == 201 and added.json()["added"] == 1  # priya@atrium.demo is the one WAITING investor here
    view = api.get("/ops/reconciliation", headers=MEI).json()
    assert len(view["receipts"]) == 2 and view["demo"] is True
    import app.auth as auth_mod

    monkeypatch.setattr(get_settings(), "auth_mode", "firebase")
    monkeypatch.setattr(auth_mod, "_verify_firebase_token",
                        lambda token: {"uid": "fb-mei", "email": "mei@atrium.demo", "email_verified": True})
    assert api.post("/ops/demo/payments", headers={"Authorization": "Bearer good"}).status_code == 404


def test_alerts_are_reviewed_and_decided_by_the_mlro(api, db, staff, account):
    alert = AmlAlert(scenario="structuring", title="Possible structuring", severity="high", score=0.9,
                     person_id=account.person_id, account_id=account.id,
                     summary="3 subscriptions between $8,500.00 and $10,000.00 within 5 days, $29,050.00 in all.",
                     evidence=[{"kind": "instruction", "id": "i1", "date": "2026-10-06", "amount": "9400.00",
                                "detail": "Subscription of $9,400.00 on October 6"}],
                     fingerprint="f" * 64)
    db.add(alert)
    db.commit()
    listed = api.get("/compliance/alerts", headers=OMAR).json()
    assert [a["title"] for a in listed] == ["Possible structuring"] and listed[0]["person"]["name"] == "Priya Raman"
    detail = api.get(f"/compliance/alerts/{alert.id}", headers=OMAR).json()
    assert detail["evidence"][0]["id"] == "i1" and {n["kind"] for n in detail["graph"]["nodes"]} >= {"person", "account"}
    api.app.dependency_overrides[get_llm] = lambda: FakeLLM({"aml_case_review": REVIEW})
    reviewed = api.post(f"/compliance/alerts/{alert.id}/review", headers=OMAR)
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["ai_review"]["triage"] == "escalate" and reviewed.json()["ai_review"]["verified"] is True
    decided = api.post(f"/compliance/alerts/{alert.id}/decide", headers=OMAR,
                       json={"decision": "escalate", "note": "Filing a SAR."})
    assert decided.status_code == 200 and decided.json()["state"] == "escalated"
    assert decided.json()["decided_by"] == "Omar Haddad"
    assert api.get("/compliance/alerts?state=escalated", headers=OMAR).json()[0]["id"] == alert.id
    log = api.get("/compliance/ai-decisions", headers=OMAR).json()
    assert log["count"] == 1 and log["decisions"][0]["purpose"] == "aml_case_review"
    assert api.post("/compliance/monitoring", headers=OMAR).status_code == 200


def test_the_demo_authenticator_is_for_staff_in_persona_sign_in_only(api, staff, monkeypatch):
    shown = api.get("/me/authenticator", headers=SAM)
    assert shown.status_code == 200, shown.text
    totp, now = pyotp.TOTP(staff["sam"].totp_secret), datetime.now(timezone.utc)
    assert shown.json()["code"] in {totp.at(now), totp.at(now - timedelta(seconds=30))}  # the code may roll over
    assert 1 <= shown.json()["seconds_left"] <= 30 and "Demo" in shown.json()["note"]
    assert api.get("/me/authenticator", headers=INVESTOR).status_code == 403
    import app.auth as auth_mod

    monkeypatch.setattr(get_settings(), "auth_mode", "firebase")
    monkeypatch.setattr(auth_mod, "_verify_firebase_token",
                        lambda token: {"uid": "fb-sam", "email": "sam@atrium.demo", "email_verified": True})
    assert api.get("/me/authenticator", headers={"Authorization": "Bearer good"}).status_code == 404


def test_on_postgres_decisions_wait_for_a_running_day_end(api, db, staff, monkeypatch):
    """Accepting a match while a day-end is dealing would leave a paid subscription dealt but never settled, so every
    decision that touches instructions or statement lines takes the day-end's lock first."""
    reference = payment_reference(db.scalar(select(Instruction.id)))
    data = f"Date,Description,Amount\n2026-10-09,ACH CREDIT PRIYA RAMAN REF {reference},1500.00\n".encode()
    api.post("/ops/statements", headers=MEI, files={"file": ("lock.csv", data, "text/csv")})
    asked = api.post("/ops/prices/publish", headers=MEI, json={"as_of": "2026-10-09", "reason": "Checked."}).json()
    locks, real_execute = [], db.execute

    def execute(statement, *args, **kwargs):
        if "pg_advisory_xact_lock" in str(statement):
            locks.append(str(statement))
            return None
        return real_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db.get_bind().dialect, "name", "postgresql")
    monkeypatch.setattr(db, "execute", execute)
    assert api.post("/ops/reconcile", headers=MEI).status_code == 200
    match_id = api.get("/ops/reconciliation", headers=MEI).json()["proposals"][0]["id"]
    assert api.post(f"/ops/matches/{match_id}/accept", headers=SAM, json={}).status_code == 200
    assert api.post(f"/ops/approvals/{asked['id']}/decide", headers=SAM,
                    json={"approve": True, "code": code(staff["sam"])}).status_code == 200
    assert api.post("/compliance/monitoring", headers=OMAR).status_code == 200
    assert len(locks) == 4 and all("day-end" in lock for lock in locks)


def test_the_four_eyes_flow_reaches_each_side_through_the_inbox(api, staff, inbox):
    asked = api.post("/ops/prices/publish", headers=MEI, json={"as_of": "2026-10-09", "reason": "Checked."}).json()
    assert [i.id for i in inbox.to(staff["sam"])] == [f"approval_requested-{asked['id']}"]
    assert inbox.to(staff["mei"]) == [] and inbox.to(staff["omar"]) == []
    wrong = api.post(f"/ops/approvals/{asked['id']}/decide", headers=SAM,
                     json={"approve": True, "code": wrong_code(staff["sam"])})
    assert wrong.status_code == 422 and inbox.to(staff["mei"]) == []
    api.post(f"/ops/approvals/{asked['id']}/decide", headers=SAM, json={"approve": True, "code": code(staff["sam"])})
    [told] = inbox.to(staff["mei"])
    assert (told.title, told.severity) == ("Sam approved your request", "info")
    assert told.body == "Publish 7 fund prices for October 9."


def test_monitoring_run_by_hand_tells_the_rest_of_compliance(api, db, staff, account, inbox):
    from app.models import Person

    lena = Person(kind="compliance", full_name="Lena Fischer", email="lena@atrium.demo")
    db.add(lena)
    now = datetime.now(timezone.utc)
    for days, amount in ((6, "9400"), (4, "9750"), (2, "9900")):
        db.add(Instruction(account_id=account.id, fund_code="ATR-CASH", type="subscribe", amount=Decimal(amount),
                           state="settled", requested_at=now - timedelta(days=days)))
    db.commit()
    raised = api.post("/compliance/monitoring", headers=OMAR).json()["alerts"]
    told = inbox.to(lena)
    assert [i.id for i in told] == [f"alert_raised-{a['id']}" for a in raised]
    structuring = next(a for a in raised if a["scenario"] == "structuring")
    notice = next(i for i in told if i.source_id == structuring["id"])
    assert (notice.title, notice.severity, notice.stage, notice.actor) == (
        "Possible structuring: Priya Raman", "urgent", "govern", "Transaction monitoring")
    assert notice.href == f"/compliance/alerts/{structuring['id']}" and notice.body == structuring["summary"]
    assert inbox.to(staff["omar"]) == []  # he ran it and is looking at the result
