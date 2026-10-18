"""The Fraud ring radar API, on the demo seeds: the lead device ring reaches Sofia Rossi's account through the seeded
link, the M. Chen ring is leads only, and Noah Williams and Aisha Khan share a bank account.

Scores worked by hand: the strongest ring has 5 members (Alex Mercer, Jordan Lee, Taylor Kim, Casey Morgan, Sofia
Rossi), 1 strong shared identifier (the device; the network they share is weak), 1 flagged member (Sofia's open
money-in-and-straight-out alert; the leads are not scored yet), Sofia's account opened two years before the leads,
and both stages: 15 * 4 + 12 * 1 + 15 * 1 + 0 + 15 = 102, capped at 100.
"""
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import select

from app.ai.llm import FakeLLM, get_llm
from app.governance.breakers import trip
from app.main import app
from app.models import Account, AccountDevice, AmlAlert, Fund, Lead, Person, RingFlag
from app.seed.funds import seed_funds
from app.seed.leads import seed_demo_leads
from app.seed.operations import seed_operations
from app.seed.rings import seed_ring_link
from app.services.devices import device_hash
from app.services.ledger import apply_posting
from app.services.pricing import publish_prices
from app.services.trust import assess_trust

TODAY = date(2026, 10, 12)
OMAR, MEI = {"X-Dev-User": "omar@atrium.demo"}, {"X-Dev-User": "mei@atrium.demo"}
INVESTORS = {"priya": "Priya Raman", "lucas": "Lucas Moreau", "hana": "Hana Sato", "tom": "Tom Becker",
             "sofia": "Sofia Rossi", "arjun": "Arjun Mehta", "grace": "Grace Li", "noah": "Noah Williams",
             "aisha": "Aisha Khan"}
RING_LEADS = {"Alex Mercer", "Jordan Lee", "Taylor Kim", "Casey Morgan"}


@pytest.fixture()
def seeded(db):
    seed_funds(db)
    days = pd.bdate_range(TODAY - timedelta(days=40), TODAY)
    for code in db.scalars(select(Fund.code)).all():
        publish_prices(db, code, pd.Series([100.0] * len(days), index=days), Decimal("1000000"))
    accounts = {}
    for n, (key, name) in enumerate(INVESTORS.items(), start=1):
        person = Person(kind="investor", full_name=name, email=f"{key}@atrium.demo", risk_band=3)
        db.add(person)
        db.flush()
        accounts[key] = Account(person_id=person.id, number=f"ACC-{n:04d}", opened_on=date(2024, 10, 1),
                                bank_last4=f"{1000 + n}")
        db.add(accounts[key])
    for email, kind, name in (("mei@atrium.demo", "ops", "Mei Tanaka"), ("omar@atrium.demo", "compliance", "Omar Haddad"),
                              ("daniel@atrium.demo", "advisor", "Daniel Okafor")):
        db.add(Person(kind=kind, full_name=name, email=email))
    db.flush()
    apply_posting(db, account_id=accounts["noah"].id, instrument="ATR-CASH", instrument_type="fund",
                  posting_type="subscription", units=Decimal("200"), cash=Decimal("-20000"), price=Decimal("100"),
                  value_date=date(2025, 1, 2), reference="SEED")
    seed_demo_leads(db)
    assert seed_operations(db, TODAY) is True
    assert seed_ring_link(db) is True
    db.commit()
    return accounts


@pytest.fixture()
def api(client, seeded):
    return client


def members_named(ring: dict) -> set[str]:
    return {m["label"] for m in ring["members"]}


def ring_named(api, *names: str) -> dict:
    return next(r for r in api.get("/compliance/rings", headers=OMAR).json()["rings"] if members_named(r) == set(names))


def test_the_seed_link_puts_the_ring_device_on_sofias_account_once(db, seeded):
    sofia = seeded["sofia"]
    device = db.scalar(select(AccountDevice).where(AccountDevice.account_id == sofia.id,
                                                   AccountDevice.device_hash == device_hash("dev-ring-0001")))
    assert device.label == "Chrome on Windows"
    assert (device.first_seen.date(), device.last_seen.date()) == (TODAY - timedelta(days=9), TODAY - timedelta(days=3))
    assert seed_ring_link(db) is False
    ring_ips = {lead.ip_hash for lead in db.scalars(select(Lead).where(Lead.device_id == "dev-ring-0001")).all()}
    assert len(ring_ips) == 1 and ring_ips != {"seed"}  # the ring's applications came from one network too


def test_only_the_mlro_sees_the_rings(api):
    assert api.get("/compliance/rings", headers=MEI).status_code == 403
    assert api.post("/compliance/rings/abc/case", headers=MEI, json={}).status_code == 403


def test_the_strongest_ring_spans_leads_and_a_client(api):
    body = api.get("/compliance/rings", headers=OMAR).json()
    strongest = body["strongest"]
    assert strongest == body["rings"][0]
    assert members_named(strongest) == RING_LEADS | {"Sofia Rossi"}
    assert strongest["stages"] == ["lead", "client"] and strongest["score"] == 100
    assert (strongest["strongest"], strongest["strongest_kind"]) == ("Device dev-…0001", "device")
    assert len(strongest["strongest_members"]) == 5 and strongest["identifiers"] == 2 and strongest["links"] == 9
    assert strongest["strong_identifiers"] == 1  # the device; the network is weak
    sofia = next(m for m in strongest["members"] if m["label"] == "Sofia Rossi")
    assert sofia["kind"] == "client" and sofia["flags"][0] == "AML: money in and straight out" and sofia["flagged"]
    assert (strongest["case_alert_id"], strongest["flagged_leads"]) == (None, 0)
    assert {frozenset(members_named(r)) for r in body["rings"]} >= {
        frozenset({"Michael Chen", "M. Chen"}), frozenset({"Noah Williams", "Aisha Khan"})}

    detail = api.get(f"/compliance/rings/{strongest['id']}", headers=OMAR).json()
    kinds = {n["kind"] for n in detail["graph"]["nodes"]}
    assert kinds == {"lead", "client", "device", "ip"}
    edges = detail["graph"]["edges"]
    assert {e["strong"] for e in edges} == {True, False} and len(edges) == 9
    assert [e["id"] for e in edges] == [f"L{n}" for n in range(1, 10)] and all(e["label"] == e["id"] for e in edges)
    weak = [e for e in edges if not e["strong"]]
    assert len(weak) == 4 and all(e["source"].startswith("lead:") for e in weak)
    assert detail["link_rows"][0]["kind"] == "device" and detail["link_rows"][-1]["strength"] == "weak"
    assert api.get("/compliance/rings/000000000000", headers=OMAR).status_code == 404


def test_the_ring_is_explained_by_gemini_and_paused_by_its_breaker(api, db):
    ring = api.get("/compliance/rings", headers=OMAR).json()["strongest"]
    fake = FakeLLM({"ring_narrative": {
        "pattern": "mule_network", "summary": "Four new leads share the device that runs Sofia Rossi's account.",
        "parts": [{"text": "The same device sent four applications and signs in to Sofia Rossi's account.",
                   "links": ["L1", "L5", "L42"]}],
        "next_checks": ["Ask Sofia Rossi who else uses the device."]}})
    app.dependency_overrides[get_llm] = lambda: fake
    try:
        out = api.post(f"/compliance/rings/{ring['id']}/narrate", headers=OMAR, json={"members": [m["id"] for m in ring["members"]]})
        assert out.status_code == 200
        body = out.json()
        assert body["narrative"]["pattern"] == "mule_network" and body["dropped_citations"] == 1
        assert body["narrative"]["parts"][0]["links"] == ["L1", "L5"] and body["model"] == "fake-llm"
        trip(db, "ring_narrator", reason="It failed validation.", by="Live checks")
        db.commit()
        paused = api.post(f"/compliance/rings/{ring['id']}/narrate", headers=OMAR, json={})
        assert paused.status_code == 503 and "Ring narrative is paused" in paused.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_llm, None)


def test_a_case_opens_once_on_the_client_with_the_most_flags(api, db, seeded):
    ring = api.get("/compliance/rings", headers=OMAR).json()["strongest"]
    seen = {"members": [m["id"] for m in ring["members"]]}
    opened = api.post(f"/compliance/rings/{ring['id']}/case", headers=OMAR, json=seen)
    assert opened.status_code == 201
    alert = db.get(AmlAlert, opened.json()["alert_id"])
    assert (alert.scenario, alert.severity, alert.state, alert.person_id, alert.account_id) == (
        "ring", "high", "open", seeded["sofia"].person_id, seeded["sofia"].id)
    assert alert.title == "Possible fraud ring of 5 identities"
    assert alert.summary == ("5 identities across leads and clients share Device dev-…0001. Opened from the fraud ring "
                             "radar by Omar Haddad.")
    assert [e["id"] for e in alert.evidence] == [f"L{n}" for n in range(1, 10)]
    assert {e["kind"] for e in alert.evidence} == {"ring_link"} and all(e["amount"] is None for e in alert.evidence)
    assert opened.json()["ring"]["case_alert_id"] == alert.id
    again = api.post(f"/compliance/rings/{ring['id']}/case", headers=OMAR, json=seen)
    assert again.status_code == 409 and "Possible fraud ring of 5 identities" in again.json()["detail"]
    page = api.get(f"/compliance/alerts/{alert.id}", headers=OMAR).json()
    assert page["evidence"][0]["kind"] == "ring_link" and page["person"]["name"] == "Sofia Rossi"
    # The ring's own case does not count as a flag on the ring: Sofia's flags stay what monitoring found.
    after = api.get("/compliance/rings", headers=OMAR).json()["strongest"]
    flags = lambda r: next(m for m in r["members"] if m["label"] == "Sofia Rossi")["flags"]  # noqa: E731
    assert after["id"] == ring["id"] and flags(after) == flags(ring)
    assert not any("fraud ring" in f for f in flags(after))


def test_a_ring_of_leads_only_has_no_one_to_open_a_case_on(api):
    chen = ring_named(api, "Michael Chen", "M. Chen")
    refused = api.post(f"/compliance/rings/{chen['id']}/case", headers=OMAR, json={})
    assert refused.status_code == 409
    assert refused.json()["detail"] == ("This ring has no client, so there is no one to open a case on; flag the "
                                        "leads instead.")


def test_flagging_the_leads_twice_flags_each_once_and_lowers_their_trust(api, db):
    ring = api.get("/compliance/rings", headers=OMAR).json()["strongest"]
    seen = {"members": [m["id"] for m in ring["members"]]}
    first = api.post(f"/compliance/rings/{ring['id']}/flag-leads", headers=OMAR, json=seen)
    assert first.status_code == 200 and first.json()["flagged"] == 4
    assert first.json()["ring"]["flagged_leads"] == 4
    second = api.post(f"/compliance/rings/{ring['id']}/flag-leads", headers=OMAR, json=seen)
    assert second.json()["flagged"] == 0
    assert len(db.scalars(select(RingFlag)).all()) == 4
    for lead in db.scalars(select(Lead).where(Lead.full_name.in_(RING_LEADS))).all():
        db.refresh(lead)
        t09 = [s for s in lead.trust_signals if s["code"] == "T09"]
        assert len(t09) == 1 and t09[0]["label"] == "Part of a fraud ring" and t09[0]["weight"] == -25
        assert t09[0]["evidence"].startswith("Flagged by Omar Haddad on ") and t09[0]["source"] == "rings"
    bank = ring_named(api, "Noah Williams", "Aisha Khan")
    assert api.post(f"/compliance/rings/{bank['id']}/flag-leads", headers=OMAR, json={}).status_code == 409


def test_a_ring_that_changed_since_it_was_seen_is_refused(api):
    ring = api.get("/compliance/rings", headers=OMAR).json()["strongest"]
    stale = {"members": [m["id"] for m in ring["members"]][:4]}
    changed = api.post(f"/compliance/rings/{ring['id']}/case", headers=OMAR, json=stale)
    assert changed.status_code == 409 and changed.json()["detail"] == "This ring has changed; reload it."
    gone = api.post("/compliance/rings/000000000000/flag-leads", headers=OMAR, json=stale)
    assert gone.status_code == 409 and gone.json()["detail"] == "This ring has changed; reload it."
    assert api.post("/compliance/rings/000000000000/case", headers=OMAR, json={}).status_code == 404


def test_t09_names_who_flagged_the_lead(db, make_lead, staff):
    lead = make_lead()
    db.add(RingFlag(lead_id=lead.id, ring_id="abcdefabcdef", flagged_by=staff["omar"].id))
    db.add(RingFlag(lead_id=lead.id, ring_id="123456123456", flagged_by=staff["omar"].id))
    db.flush()
    report = assess_trust(db, lead, None, None)
    [signal] = [s for s in report.signals if s.code == "T09"]  # two rings, one signal
    flagged = db.scalars(select(RingFlag)).first().created_at
    assert signal.evidence == f"Flagged by Omar Haddad on {flagged:%B} {flagged.day}, {flagged.year}"
    assert report.score == 100 - 25 and report.band == "review"


def test_a_case_tells_the_rest_of_compliance(api, db, inbox):
    lena = Person(kind="compliance", full_name="Lena Fischer", email="lena@atrium.demo")
    db.add(lena)
    db.commit()
    ring = api.get("/compliance/rings", headers=OMAR).json()["strongest"]
    opened = api.post(f"/compliance/rings/{ring['id']}/case", headers=OMAR,
                      json={"members": [m["id"] for m in ring["members"]]}).json()
    [told] = inbox.to(lena)
    assert (told.id, told.href, told.severity, told.actor) == (
        f"alert_raised-{opened['alert_id']}", f"/compliance/alerts/{opened['alert_id']}", "urgent", "Omar Haddad")
    assert told.title == "Possible fraud ring of 5 identities: Sofia Rossi"
    omar = db.scalar(select(Person).where(Person.email == "omar@atrium.demo"))
    assert inbox.to(omar) == []  # he opened it


def test_flagged_ring_leads_that_turn_high_risk_reach_the_advisors(api, db, inbox):
    ring = api.get("/compliance/rings", headers=OMAR).json()["strongest"]
    api.post(f"/compliance/rings/{ring['id']}/flag-leads", headers=OMAR,
             json={"members": [m["id"] for m in ring["members"]]})
    daniel = db.scalar(select(Person).where(Person.email == "daniel@atrium.demo"))
    held = {lead.id: lead for lead in db.scalars(select(Lead).where(Lead.full_name.in_(RING_LEADS))).all()
            if lead.trust_band in ("high_risk", "blocked")}
    assert held, "the ring's leads should cross into high risk once flagged"
    assert sorted(i.source_id for i in inbox.to(daniel)) == sorted(held)
    assert all(i.href == f"/advisor/leads/{i.source_id}" and i.actor == "Trust Score" for i in inbox.to(daniel))
