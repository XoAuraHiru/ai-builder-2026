from datetime import datetime, timedelta, timezone

import pyotp
import pytest

from app.models import Person
from app.services.approvals import (ApprovalError, current_code, decide, ensure_totp_secret, payload_hash,
                                    request_approval, verify_code)

NOW = datetime(2026, 10, 12, 15, tzinfo=timezone.utc)


def code_for(person, at=NOW):
    return pyotp.TOTP(person.totp_secret).at(at)


def ask(db, staff, reason="Checked against the market."):
    return request_approval(db, action="publish_prices",
                            payload={"as_of": "2026-10-09", "prices": {"ATR-BAL": "101.000000"}},
                            summary="Publish 1 price for October 9", reason=reason,
                            evidence=[{"label": "Atrium Balanced", "detail": "Moved +1.0%."}], requested_by=staff["mei"])


def recorder(calls):
    def executor(session, approval, approver, now):
        calls.append(approver.email)
        return {"published": 1}

    return executor


def test_a_request_needs_a_reason_and_fixes_its_payload(db, staff):
    with pytest.raises(ApprovalError, match="Give a reason"):
        ask(db, staff, reason="  ")
    approval = ask(db, staff)
    assert approval.state == "pending" and approval.payload_hash == payload_hash(approval.payload)


def test_only_a_different_operations_person_with_a_current_code_can_approve(db, staff):
    approval, calls = ask(db, staff), []
    run = recorder(calls)
    with pytest.raises(ApprovalError, match="different person"):
        decide(db, approval, staff["mei"], approve=True, code=code_for(staff["mei"]), now=NOW, executor=run)
    with pytest.raises(ApprovalError, match="Only operations staff"):
        decide(db, approval, staff["omar"], approve=True, code=code_for(staff["omar"]), now=NOW, executor=run)
    with pytest.raises(ApprovalError, match="code is not right"):
        decide(db, approval, staff["sam"], approve=True, code="12345", now=NOW, executor=run)
    stale = code_for(staff["sam"], NOW - timedelta(minutes=5))
    with pytest.raises(ApprovalError, match="code is not right"):
        decide(db, approval, staff["sam"], approve=True, code=stale, now=NOW, executor=run)
    assert approval.state == "pending" and calls == []
    decide(db, approval, staff["sam"], approve=True, code=code_for(staff["sam"]), note="Matches the market.", now=NOW,
           executor=run)
    assert (approval.state, approval.decided_by, approval.result) == ("approved", staff["sam"].id, {"published": 1})
    assert calls == ["sam@atrium.demo"] and approval.step_up_verified_at == NOW
    assert approval.decision_note == "Matches the market."
    with pytest.raises(ApprovalError, match="already been decided"):
        decide(db, approval, staff["sam"], approve=True, code=code_for(staff["sam"]), now=NOW, executor=run)


def test_rejecting_runs_nothing(db, staff):
    approval, calls = ask(db, staff), []
    decide(db, approval, staff["sam"], approve=False, code=code_for(staff["sam"]), note="Wrong date.", now=NOW,
           executor=recorder(calls))
    assert approval.state == "rejected" and approval.result is None and calls == []


def test_a_changed_payload_cannot_be_approved(db, staff):
    approval = ask(db, staff)
    approval.payload = {**approval.payload, "prices": {"ATR-BAL": "999.000000"}}
    with pytest.raises(ApprovalError, match="changed after"):
        decide(db, approval, staff["sam"], approve=True, code=code_for(staff["sam"]), now=NOW,
               executor=recorder([]))


def test_the_demo_authenticator_shows_the_current_code(db, staff):
    code, seconds_left = current_code(staff["sam"], NOW)
    assert verify_code(staff["sam"], code, NOW) and verify_code(staff["sam"], f"{code[:3]} {code[3:]}", NOW)
    assert 0 < seconds_left <= 30
    newcomer = Person(kind="ops", full_name="New Hire", email="new@atrium.demo")
    assert not verify_code(newcomer, "123456", NOW)
    assert len(ensure_totp_secret(newcomer)) == 32 and newcomer.totp_secret


def test_a_request_tells_the_other_approvers_and_its_decision_tells_the_requester(db, staff, inbox):
    approval = ask(db, staff)
    db.commit()
    [asked] = inbox.to(staff["sam"])
    assert (asked.id, asked.stage, asked.severity, asked.href) == (
        f"approval_requested-{approval.id}", "operate", "attention", "/operations/approvals")
    assert (asked.title, asked.actor) == ("Mei asks for your approval", "Mei Tanaka")
    assert asked.body == "Publish 1 price for October 9. Reason: Checked against the market."
    assert inbox.to(staff["mei"]) == [] and inbox.to(staff["omar"]) == []  # never the requester; only approvers
    decide(db, approval, staff["sam"], approve=False, code=code_for(staff["sam"]), note="Wrong date.", now=NOW,
           executor=recorder([]))
    db.commit()
    [told] = inbox.to(staff["mei"])
    assert (told.id, told.title, told.severity, told.actor) == (
        f"approval_decided-{approval.id}", "Sam rejected your request", "attention", "Sam Ortiz")
    assert told.body == "Publish 1 price for October 9. Note: Wrong date."


def test_a_decision_that_is_rolled_back_tells_no_one(db, staff, inbox):
    approval = ask(db, staff)
    db.commit()
    decide(db, approval, staff["sam"], approve=True, code=code_for(staff["sam"]), now=NOW, executor=recorder([]))
    db.rollback()
    db.commit()
    assert inbox.kinds() == ["approval_requested"]
