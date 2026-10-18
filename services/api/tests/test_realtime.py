"""The live inbox: notices leave only once their transaction commits, reach each person once, never fail a request,
and each browser gets a Firestore session for its own person's inbox and nothing more."""
import logging
import threading
from datetime import timedelta

import pytest

from app.config import get_settings
from app.models import IdentityCheck
from app.models.base import utcnow
from app.realtime import firebase as fb
from app.realtime import inbox as inbox_module
from app.realtime.inbox import BATCH, Courier, Delivery, FirestoreSink, Item, courier, notify, people, set_courier
from app.services.trust import apply_trust

MEI, OMAR = {"X-Dev-User": "mei@atrium.demo"}, {"X-Dev-User": "omar@atrium.demo"}


def item(n: str = "1", **changes) -> Item:
    fields = dict(kind="test", source_id=n, stage="operate", title=f"Notice {n}", body="Something happened.",
                  href="/operations", severity="info", actor="Day-end")
    return Item(**{**fields, **changes})


def test_an_item_leaves_only_when_its_transaction_commits(db, staff, inbox):
    notify(db, people(db, "ops"), item())
    db.flush()
    assert inbox.sent == []
    db.commit()
    assert sorted((d.person_id, d.item.id) for d in inbox.sent) == sorted([(staff["mei"].id, "test-1"),
                                                                          (staff["sam"].id, "test-1")])


def test_a_rollback_sends_nothing(db, staff, inbox):
    notify(db, people(db, "ops"), item())
    db.rollback()
    db.commit()
    assert inbox.sent == []


def test_a_savepoint_that_rolls_back_takes_back_only_what_was_staged_inside_it(db, staff, inbox):
    ops = people(db, "ops")
    notify(db, ops, item("outer"))
    with db.begin_nested():
        notify(db, ops, item("kept"))
    with pytest.raises(RuntimeError):
        with db.begin_nested():
            notify(db, ops, item("undone"))
            raise RuntimeError("the savepoint fails")
    assert inbox.sent == []  # releasing a savepoint is not the commit
    db.commit()
    assert sorted({d.item.id for d in inbox.sent}) == ["test-kept", "test-outer"]


def test_the_same_notice_twice_in_one_transaction_goes_once_as_last_staged(db, staff, inbox):
    mei = staff["mei"].id
    notify(db, [mei], item())
    notify(db, [mei, mei], item(title="Notice 1, updated"))
    db.commit()
    assert [(d.person_id, d.item.title) for d in inbox.sent] == [(mei, "Notice 1, updated")]


def test_nothing_is_staged_while_the_inbox_is_off(db, staff, inbox):
    set_courier(None)
    notify(db, people(db, "ops"), item())
    set_courier(Courier(inbox, background=False))  # switched on before the commit: what was skipped stays skipped
    db.commit()
    assert inbox.sent == []


def test_the_inbox_follows_its_setting(monkeypatch):
    monkeypatch.setattr(inbox_module, "_configured", False)
    monkeypatch.setattr(get_settings(), "firestore_enabled", False)
    assert courier() is None
    monkeypatch.setattr(inbox_module, "_configured", False)
    monkeypatch.setattr(get_settings(), "firestore_enabled", True)
    made = courier()
    assert isinstance(made, Courier) and isinstance(made.sink, FirestoreSink)


def test_an_item_names_its_stage_its_severity_and_an_app_route():
    assert item().id == "test-1" and item().fields()["href"] == "/operations"
    for bad in ({"stage": "later"}, {"severity": "loud"}, {"href": "https://example.test/x"}):
        with pytest.raises(ValueError):
            item(**bad)


def test_the_courier_writes_off_the_request_thread_and_a_job_can_wait_for_it():
    seen = []

    class Sink:
        def write(self, deliveries):
            seen.append((threading.current_thread().name, [d.item.id for d in deliveries]))

    courier_ = Courier(Sink())
    courier_.send([Delivery("p1", item())])
    courier_.drain()
    assert len(seen) == 1 and seen[0][0].startswith("inbox") and seen[0][1] == ["test-1"]


def test_a_failed_write_is_logged_and_never_raised(caplog):
    class Down:
        def write(self, deliveries):
            raise RuntimeError("Firestore is unavailable")

    with caplog.at_level(logging.ERROR, logger="app.realtime.inbox"):
        Courier(Down(), background=False).send([Delivery("p1", item())])
    assert "1 notice(s) not delivered" in caplog.text


def test_a_failing_inbox_never_fails_the_request(client, staff, people, caplog):
    class Down:
        def write(self, deliveries):
            raise RuntimeError("Firestore is unavailable")

    set_courier(Courier(Down(), background=False))
    with caplog.at_level(logging.ERROR, logger="app.realtime.inbox"):
        r = client.post("/governance/breakers/lead_enrichment/open", headers=OMAR, json={"reason": "Kill switch test."})
    assert r.status_code == 200 and r.json()["state"] == "open"
    assert "not delivered" in caplog.text  # Daniel owns the model, so there was a notice to lose


class FakeFirestore:
    """Just enough of the Firestore client to see the paths and documents a batch writes."""

    class Ref:
        def __init__(self, path):
            self.path = path

        def collection(self, name):
            return FakeFirestore.Ref(f"{self.path}/{name}")

        def document(self, name):
            return FakeFirestore.Ref(f"{self.path}/{name}")

    class Batch:
        def __init__(self, commits):
            self.commits, self.writes = commits, []

        def set(self, ref, data):
            self.writes.append((ref.path, data))

        def commit(self):
            self.commits.append(self.writes)

    def __init__(self):
        self.commits = []

    def collection(self, name):
        return FakeFirestore.Ref(name)

    def batch(self):
        return FakeFirestore.Batch(self.commits)


def test_firestore_gets_one_document_per_person_and_item_in_batches():
    from firebase_admin import firestore

    sink, store = FirestoreSink(), FakeFirestore()
    sink._client = store
    sink.write([Delivery(f"p{n}", item(str(n))) for n in range(BATCH + 1)])
    assert [len(writes) for writes in store.commits] == [BATCH, 1]
    path, document = store.commits[0][0]
    assert path == "people/p0/inbox/test-0"
    assert document == {"kind": "test", "stage": "operate", "title": "Notice 0", "body": "Something happened.",
                        "href": "/operations", "severity": "info", "actor": "Day-end", "read": False,
                        "created_at": firestore.SERVER_TIMESTAMP}


def test_the_realtime_session_is_off_by_default(client, staff):
    r = client.get("/me/realtime", headers=MEI)
    assert r.status_code == 200 and r.json() == {"enabled": False, "token": None, "path": None, "project_id": None}


def test_the_realtime_session_signs_the_browser_in_as_its_own_person(client, staff, monkeypatch):
    minted = []
    monkeypatch.setattr(get_settings(), "firestore_enabled", True)
    monkeypatch.setattr(get_settings(), "gcp_project", "atrium-test")
    monkeypatch.setattr("app.routers.me.custom_token", lambda pid, role: minted.append((pid, role)) or "signed")
    mei = staff["mei"].id
    assert client.get("/me/realtime", headers=MEI).json() == {
        "enabled": True, "token": "signed", "path": f"people/{mei}/inbox", "project_id": "atrium-test"}
    assert minted == [(mei, "ops")]
    assert client.get("/me/realtime").status_code == 401


def test_a_token_that_cannot_be_made_turns_the_inbox_off_not_the_page(client, staff, monkeypatch, caplog):
    def refuse(pid, role):
        raise PermissionError("iam.serviceAccounts.signBlob denied")

    monkeypatch.setattr(get_settings(), "firestore_enabled", True)
    monkeypatch.setattr("app.routers.me.custom_token", refuse)
    with caplog.at_level(logging.ERROR, logger="app.routers.me"):
        r = client.get("/me/realtime", headers=MEI)
    assert r.status_code == 200 and r.json()["enabled"] is False and r.json()["token"] is None
    assert "no custom token" in caplog.text


def test_a_custom_token_names_the_person_and_carries_their_role(monkeypatch):
    from firebase_admin import auth

    calls = []
    monkeypatch.setattr(fb, "firebase_app", lambda: "the-app")
    monkeypatch.setattr(auth, "create_custom_token",
                        lambda uid, claims, app=None: calls.append((uid, claims, app)) or b"signed-token")
    assert fb.custom_token("abc123", "advisor") == "signed-token"
    assert calls == [("person-abc123", {"pid": "abc123", "role": "advisor"}, "the-app")]


def test_one_firebase_app_serves_sign_in_and_the_inbox(monkeypatch):
    import firebase_admin
    from firebase_admin import auth

    made = []

    def get_app():
        if not made:
            raise ValueError("The default Firebase app does not exist.")
        return made[0]

    monkeypatch.setattr(firebase_admin, "get_app", get_app)
    monkeypatch.setattr(firebase_admin, "initialize_app", lambda options=None: made.append(("app", options)) or made[0])
    monkeypatch.setattr(get_settings(), "gcp_project", "atrium-test")
    monkeypatch.setattr(get_settings(), "firebase_service_account", "atrium-api@atrium-test.iam.gserviceaccount.com")
    assert fb.firebase_app() is fb.firebase_app() and len(made) == 1
    assert made[0][1] == {"projectId": "atrium-test",
                          "serviceAccountId": "atrium-api@atrium-test.iam.gserviceaccount.com"}

    from app.auth import _verify_firebase_token

    monkeypatch.setattr(auth, "verify_id_token", lambda token, app=None: {"uid": "u1", "app": app})
    assert _verify_firebase_token("id-token") == {"uid": "u1", "app": made[0]}


def identity_check(lead, *findings, minutes=0):
    return IdentityCheck(lead_id=lead.id, mime_type="image/png", size_bytes=1, sha256="0" * 64, extracted={},
                         findings=[{"code": code, "label": label, "weight": weight, "evidence": "From the document.",
                                    "source": "documentai", "blocking": blocking}
                                   for code, label, weight, blocking in findings],
                         source="gemini+documentai", created_at=utcnow() + timedelta(minutes=minutes))


def test_a_lead_blocked_by_its_identity_check_tells_every_advisor_once(db, make_lead, people, inbox):
    lead = make_lead()
    db.add(identity_check(lead, ("I04", "Possible image manipulation", -40, True)))
    db.flush()
    apply_trust(db, lead)
    assert inbox.sent == []
    db.commit()
    [told] = inbox.to(people["advisor"])
    assert (told.id, told.kind, told.stage, told.severity) == (f"lead_blocked-{lead.id}", "lead_blocked", "acquire",
                                                                "urgent")
    assert (told.title, told.href, told.actor) == ("Lead blocked: Ava Thompson", f"/advisor/leads/{lead.id}",
                                                   "Trust Score")
    assert told.body == "Trust score 60 of 100: possible image manipulation."
    assert inbox.to(people["investor"]) == []
    apply_trust(db, lead)  # the same band again is not news
    db.add(identity_check(lead, ("I01", "Name does not match the form", -30, False),
                          ("I06", "Suspicious words on document", -20, False),
                          ("I07", "Document could not be read reliably", -10, False), minutes=1))
    db.flush()
    apply_trust(db, lead)  # easing from blocked to high risk is not news either
    db.commit()
    assert lead.trust_band == "high_risk" and len(inbox.sent) == 1


def test_leads_scored_high_risk_are_held_for_review_and_a_clear_one_is_quiet(db, make_lead, people, inbox):
    clean = make_lead(email="clean@example.test", phone="+14155550100", device_id="dev-clean")
    farm = [make_lead(full_name=f"Lee Novak {n}", email="lee@mailinator.com", phone="+14155550199",
                      device_id="dev-farm") for n in range(3)]
    for lead in (clean, *farm):
        apply_trust(db, lead)
    db.commit()
    told = inbox.to(people["advisor"])
    assert [t.id for t in told] == [f"lead_held-{lead.id}" for lead in farm]
    assert told[0].title == "Lead held for review: Lee Novak 0" and told[0].severity == "attention"
    assert told[0].body == ("Trust score 25 of 100: disposable email domain, contact shared with another lead and "
                            "many leads from one device.")
    assert clean.trust_band == "clear"
