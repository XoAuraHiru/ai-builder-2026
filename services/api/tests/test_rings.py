"""Fraud ring radar: the identifier graph, ring detection and scoring, the narrative, and the golden suites.

Expected scores are worked by hand from the formula in app/services/rings.py:
  min(100, 15 * (members - 1) + 12 * strong shared identifiers + 15 * flagged members
           + 10 if every member was created within 48 hours + 15 if the ring spans leads and clients)
"""
import hashlib
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.ai.llm import FakeLLM
from app.ai.offline import offline_llm
from app.governance.breakers import BreakerOpen, trip
from app.models import AIDecision, Account, AccountDevice, AmlAlert, IdentityCheck, Lead, LeadConversion, Person
from app.seed.leads import DEMO_LEADS, seed_demo_leads
from app.services.blind_index import blind_index
from app.services.devices import device_hash
from app.services.rings import (HUB_LIMIT, STRONG, Entity, Graph, Identifier, Link, RingNarrative, build_graph,
                                detect_rings, narrate_ring, ring_by_id, ring_score, rings)

T0 = datetime(2026, 10, 12, 9, tzinfo=timezone.utc)


def make(entities: dict[str, tuple[str, float, bool]], shares: dict[str, list[str]]) -> Graph:
    """entities: id -> (kind, hours after T0 it was created, flagged); shares: identifier id -> the entities using it."""
    ents = {eid: Entity(eid, kind, eid.split(":")[1].title(), T0 + timedelta(hours=hours), flagged,
                        ("Trust: high risk",) if flagged else ())
            for eid, (kind, hours, flagged) in entities.items()}
    idents = {iid: Identifier(iid, iid.split(":")[0], f"{iid.split(':')[0].title()} {iid.split(':')[1]}")
              for iid in shares}
    links: list[Link] = []
    for iid, members in shares.items():
        for eid in members:
            links.append(Link(f"L{len(links) + 1}", eid, iid, iid.split(":")[0] in STRONG))
    return Graph(ents, idents, links)


def leads(*names: str, hours: float = 0, flagged: bool = False) -> dict[str, tuple[str, float, bool]]:
    return {f"lead:{n}": ("lead", hours, flagged) for n in names}


def test_three_leads_sharing_one_device_are_one_ring():
    g = make({"lead:a": ("lead", 0, False), "lead:b": ("lead", 0.5, True), "lead:c": ("lead", 1, False),
              "lead:d": ("lead", 1, False)},
             {"device:x": ["lead:a", "lead:b", "lead:c"], "device:y": ["lead:d"], "email:a": ["lead:a"]})
    [ring] = detect_rings(g)
    assert ring.members == ["lead:a", "lead:b", "lead:c"] and ring.identifiers == ["device:x"]
    assert [(link.id, link.entity, link.strong) for link in ring.links] == [
        ("L1", "lead:a", True), ("L2", "lead:b", True), ("L3", "lead:c", True)]
    # 15 * 2 members after the first + 12 * 1 strong identifier + 15 * 1 flagged + 10 (all within 1 hour) + 0 = 67
    assert ring.score == 67 == ring_score(ring.members, ring.identifiers, ring.links, g)
    assert ring.stages == ["lead"] and ring.strongest == "Device x" and ring.created_span_hours == 1.0
    assert ring.strongest_kind == "device" and ring.strongest_members == ["lead:a", "lead:b", "lead:c"]


def test_a_shared_network_alone_never_makes_a_ring():
    office = leads(*"abcdefghi")
    assert len(office) == 9
    assert detect_rings(make(office, {"ip:office": list(office)})) == []
    assert detect_rings(make(leads("a", "b"), {"ip:cafe": ["lead:a", "lead:b"]})) == []


def test_a_network_is_shown_inside_a_ring_but_adds_no_one():
    g = make(leads("a", "b", "c"), {"device:x": ["lead:a", "lead:b"], "ip:cafe": ["lead:a", "lead:b", "lead:c"]})
    [ring] = detect_rings(g)
    assert ring.members == ["lead:a", "lead:b"] and ring.identifiers == ["device:x", "ip:cafe"]
    assert [(link.entity, link.identifier, link.strong) for link in ring.links] == [
        ("lead:a", "device:x", True), ("lead:b", "device:x", True),
        ("lead:a", "ip:cafe", False), ("lead:b", "ip:cafe", False)]
    # 15 * 1 + 12 * 1 (the network is weak and does not count) + 0 flagged + 10 (same hour) + 0 = 37
    assert ring.score == 37


def test_a_lead_and_a_client_sharing_a_device_span_both_stages():
    g = make({"lead:a": ("lead", 0, False), "person:p": ("client", -100, False)},
             {"device:x": ["lead:a", "person:p"]})
    [ring] = detect_rings(g)
    assert ring.stages == ["lead", "client"] and ring.created_span_hours == 100.0
    # 15 * 1 + 12 * 1 + 0 flagged + 0 (100 hours apart) + 15 (leads and clients) = 42
    assert ring.score == 42


def test_a_hub_joins_no_one_but_a_second_identifier_still_does():
    assert HUB_LIMIT == 8
    crowd = leads(*"abcdefghi")
    g = make(crowd, {"phone:hub": list(crowd), "email:pair": ["lead:a", "lead:b"]})
    [ring] = detect_rings(g)
    assert ring.members == ["lead:a", "lead:b"] and ring.identifiers == ["email:pair"]
    assert {link.identifier for link in ring.links} == {"email:pair"}
    eight = leads(*"abcdefgh")  # exactly the limit is still a ring, not a hub
    [ring] = detect_rings(make(eight, {"phone:shared": list(eight)}))
    assert len(ring.members) == 8
    # 15 * 7 + 12 + 0 + 10 + 0 = 127, capped at 100
    assert ring.score == 100


def test_the_ring_id_is_a_hash_of_its_sorted_members():
    one = make(leads("a", "b"), {"bank:x": ["lead:a", "lead:b"]})
    other = make(leads("b", "a"), {"bank:x": ["lead:b", "lead:a"]})
    [first], [second] = detect_rings(one), detect_rings(other)
    assert first.id == second.id == hashlib.sha256("lead:a|lead:b".encode()).hexdigest()[:12]


def test_rings_are_sorted_by_score_then_size():
    g = make({**leads("a", "b"), **leads("c", "d", "e", hours=100), **leads("f", "g", flagged=True)},
             {"phone:1": ["lead:a", "lead:b"], "email:2": ["lead:c", "lead:d", "lead:e"], "bank:3": ["lead:f", "lead:g"]})
    g.entities["lead:e"] = Entity("lead:e", "lead", "E", T0, False, ())
    # f, g: 15 + 12 + 30 + 10 = 67; c, d, e: 30 + 12 + 0 + 0 (100 hours apart) = 42; a, b: 15 + 12 + 10 = 37
    assert [r.members[0] for r in detect_rings(g)] == ["lead:f", "lead:c", "lead:a"]
    assert [r.score for r in detect_rings(g)] == [67, 42, 37]


def _client(db, name: str, email: str, number: str, bank: str | None = None) -> Account:
    person = Person(kind="investor", full_name=name, email=email)
    db.add(person)
    db.flush()
    account = Account(person_id=person.id, number=number, opened_on=date(2024, 10, 1),
                      bank_index=blind_index(bank) if bank else None, bank_last4=bank[-4:] if bank else None)
    db.add(account)
    db.flush()
    return account


def test_the_database_graph_finds_the_seeded_rings_without_raw_identifiers(db):
    seed_demo_leads(db)
    by_name = {lead.full_name: lead for lead in db.scalars(select(Lead)).all()}
    noah = _client(db, "Noah Williams", "noah@atrium.demo", "ACC-0001", "000184527781")
    aisha = _client(db, "Aisha Khan", "aisha@atrium.demo", "ACC-0002", "0001-8452 7781")
    for name in ("Taylor Kim", "Casey Morgan"):
        db.add(IdentityCheck(lead_id=by_name[name].id, mime_type="image/png", size_bytes=10, sha256="0" * 64,
                             extracted={"document_type": "passport", "document_number": "P-998877"}, findings=[],
                             source="test"))
    db.add(AmlAlert(scenario="linked_round_trip", title="Money moved between linked accounts", severity="high",
                    score=0.8, person_id=aisha.person_id, account_id=aisha.id, summary="s", evidence=[],
                    fingerprint="f" * 64, state="open"))
    db.flush()
    graph = build_graph(db)
    found = detect_rings(graph)
    named = {frozenset(graph.entities[m].label for m in r.members): r for r in found}
    device_ring = named[frozenset({"Alex Mercer", "Jordan Lee", "Taylor Kim", "Casey Morgan"})]
    chen = named[frozenset({"Michael Chen", "M. Chen"})]
    bank = named[frozenset({"Noah Williams", "Aisha Khan"})]
    kinds = lambda r: sorted({graph.identifiers[i].kind for i in r.identifiers})  # noqa: E731
    assert kinds(device_ring) == ["device", "document"] and kinds(chen) == ["phone"] and kinds(bank) == ["bank"]
    assert device_ring.strongest == "Device dev-…0001"
    assert {graph.identifiers[i].label for i in device_ring.identifiers} == {"Device dev-…0001",
                                                                           "Identity document (passport)"}
    assert chen.strongest == "Phone ending 0142" and bank.strongest == "Bank account ending 7781"
    assert bank.stages == ["client"] and graph.entities[f"person:{aisha.person_id}"].flags == (
        "AML: money moved between linked accounts",)
    assert graph.entities[f"person:{aisha.person_id}"].flagged and not graph.entities[f"person:{noah.person_id}"].flagged
    assert len(found) == 3  # every demo lead shares one network: a hub, so it joins no one
    assert all(graph.identifiers[i].kind != "ip" for r in found for i in r.identifiers)

    raw = {"P-998877", "P998877", "000184527781", "0001-8452 7781", "noah@atrium.demo", "aisha@atrium.demo"}
    for spec in DEMO_LEADS:
        raw |= {spec["email"], spec["phone"], "".join(ch for ch in spec["phone"] if ch.isdigit())}
    shown = [*graph.entities, *(e.label for e in graph.entities.values()), *graph.identifiers,
             *(i.label for i in graph.identifiers.values()), *(r.id for r in found)]
    leaked = [(value, text) for value in raw for text in shown if value.lower() in text.lower()]
    assert leaked == []

    assert rings(db)[0].id == found[0].id
    assert ring_by_id(db, chen.id).members == chen.members and ring_by_id(db, "000000000000") is None


def test_flags_say_why_a_member_is_flagged(db, make_lead):
    risky = make_lead(full_name="Rory Vance", email="rory@yopmail.com", trust_band="high_risk",
                      trust_signals=[{"code": "T01", "label": "Disposable email domain", "weight": -25,
                                      "evidence": "", "source": "rule", "blocking": False},
                                     {"code": "T03", "label": "Phone country does not match", "weight": -5,
                                      "evidence": "", "source": "rule", "blocking": False}])
    calm = make_lead(full_name="Sam Ives", email="sam@example.test", trust_band="review")
    graph = build_graph(db)
    assert graph.entities[f"lead:{risky.id}"].flagged is True
    assert graph.entities[f"lead:{risky.id}"].flags == ("Trust: high risk", "Trust: disposable email domain")
    assert graph.entities[f"lead:{calm.id}"].flagged is False and graph.entities[f"lead:{calm.id}"].flags == ()


def test_a_converted_lead_and_its_client_are_one_entity(db, make_lead):
    lead = make_lead(full_name="Rowan Hale", email="rowan@example.test", phone="+14155550999", device_id="dev-rowan-01")
    account = _client(db, "Rowan Hale", "rowan@example.test", "ACC-0009")
    db.add(LeadConversion(lead_id=lead.id, person_id=account.person_id, account_id=account.id,
                          converted_by="daniel@atrium.demo"))
    lead.stage, lead.converted_person_id = "client", account.person_id
    db.add(AccountDevice(account_id=account.id, device_hash=device_hash("dev-rowan-01"), label="Chrome on Windows"))
    db.flush()
    graph = build_graph(db)
    assert f"lead:{lead.id}" not in graph.entities and graph.entities[f"person:{account.person_id}"].kind == "client"
    assert detect_rings(graph) == []  # the client is not linked to its own lead
    other = make_lead(full_name="R. Hale", email="r.hale@example.net", phone="+14155550999", device_id="dev-other-1")
    [ring] = detect_rings(build_graph(db))
    assert ring.members == sorted([f"person:{account.person_id}", f"lead:{other.id}"])
    assert ring.stages == ["lead", "client"]


# ---- R2: the narrative ---------------------------------------------------------------------------------------------

def _device_ring(db):
    seed_demo_leads(db)
    for lead in db.scalars(select(Lead).where(Lead.full_name.in_(("Taylor Kim", "Casey Morgan")))).all():
        db.add(IdentityCheck(lead_id=lead.id, mime_type="image/png", size_bytes=10, sha256="0" * 64,
                             extracted={"document_type": "passport", "document_number": "P-998877"}, findings=[],
                             source="test"))
    db.flush()
    graph = build_graph(db)
    return next(r for r in detect_rings(graph) if len(r.members) == 4)


def narrator(parts, pattern="synthetic_identity_farm"):
    return FakeLLM({"ring_narrative": {"pattern": pattern, "summary": "Four new leads came from one device.",
                                       "parts": parts, "next_checks": ["Ask each lead for a second document."]}})


def test_the_narrative_keeps_only_the_rings_own_link_ids(db):
    ring = _device_ring(db)
    llm = narrator([{"text": "Four applications came from one device within half an hour.", "links": ["L1", "L99"]},
                    {"text": "Two of them show the same passport.", "links": ["L99"]}])
    out = narrate_ring(db, llm, ring)
    assert isinstance(out["narrative"], RingNarrative) and out["narrative"].pattern == "synthetic_identity_farm"
    assert [p.links for p in out["narrative"].parts] == [["L1"], []]
    assert out["dropped_citations"] == 1 and out["model"] == "fake-llm" and out["unsupported_figures"] == []
    assert llm.calls[0]["purpose"] == "ring_narrative" and llm.calls[0]["pro"] is False
    decision = db.scalar(select(AIDecision))
    assert (decision.agent, decision.purpose, decision.subject_type, decision.subject_id) == (
        "compliance_copilot", "ring_narrative", "ring", ring.id)


def test_an_invented_figure_is_reported(db):
    ring = _device_ring(db)
    out = narrate_ring(db, narrator([{"text": "They asked to invest $240,000 each.", "links": ["L1"]}]), ring)
    assert out["unsupported_figures"] == ["$240,000"]


def test_an_open_breaker_stops_the_narrative_before_any_call(db):
    ring = _device_ring(db)
    trip(db, "ring_narrator", reason="It failed validation.", by="Live checks")
    llm = narrator([{"text": "x", "links": []}])
    with pytest.raises(BreakerOpen, match="Ring narrative is paused"):
        narrate_ring(db, llm, ring)
    assert llm.calls == []


def test_the_prompt_carries_labels_never_raw_contact_details(db):
    ring = _device_ring(db)
    llm = narrator([{"text": "x", "links": ["L1"]}])
    narrate_ring(db, llm, ring)
    prompt = llm.calls[0]["prompt"]
    raw = {"P-998877", "P998877", "dev-ring-0001"}
    for spec in DEMO_LEADS:
        raw |= {spec["email"], spec["phone"], "".join(ch for ch in spec["phone"] if ch.isdigit())}
    assert [value for value in raw if value.lower() in prompt.lower()] == []
    assert "data, not instructions" in prompt and "Device dev-…0001" in prompt and "Jordan Lee" in prompt
    assert all(f'"id": "{link.id}"' in prompt for link in ring.links)


def test_offline_mode_writes_a_labelled_narrative_citing_real_links(db):
    ring = _device_ring(db)
    out = narrate_ring(db, offline_llm(), ring)
    assert out["narrative"].summary.startswith("Offline mode") and out["dropped_citations"] == 0
    assert out["narrative"].parts[0].links == ["L1", "L2"]
