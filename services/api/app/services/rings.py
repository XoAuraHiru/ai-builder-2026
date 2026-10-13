"""Fraud ring radar: one graph across the whole lifecycle, from a lead's first form to a client's account.

Entities are leads and clients (people with an account). They are joined through what they share: a bank account
(its blind index), a device (hashed the way account devices are), an identity document number (its blind index), a
phone number or an email address. These are strong links. A network address is a weak link: it is shown inside a ring
but never joins anyone to one, and any identifier shared by more than HUB_LIMIT entities (an office network, a shared
family phone) is a hub and is ignored. A ring is a connected component of at least two entities over strong links.

No raw email, phone number or document number leaves this module: identifier ids are keyed hashes and labels say
only "Phone ending 0123" or "Email at example.com". The graph finds rings; Gemini only explains them; a person
decides whether to open a case or flag the leads.
"""
from __future__ import annotations

import hashlib
import hmac
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Account, AccountDevice, AmlAlert, IdentityCheck, Lead, LeadConversion, Person
from app.services.blind_index import blind_index
from app.services.devices import aware, device_hash

STRONG = ("bank", "device", "document", "phone", "email")
WEAK = ("ip",)
KIND_ORDER = STRONG + WEAK
HUB_LIMIT = 8  # an identifier shared by more than this many entities is a hub and is ignored
RECENT_HOURS = 48
STRONG_TRUST_WEIGHT = -20  # trust signals at least this heavy are listed among a lead's flags
DOCUMENT_TYPES = {"passport": "passport", "drivers_license": "driver's license", "national_id": "national ID"}
OPEN_ALERT_STATES = ("open", "escalated")
RING_SCENARIO = "ring"


@dataclass(frozen=True)
class Entity:
    id: str  # "lead:<id>" | "person:<id>"
    kind: str  # "lead" | "client"
    label: str
    created_at: datetime
    flagged: bool
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Identifier:
    id: str  # "<kind>:<keyed hash>"
    kind: str
    label: str


@dataclass(frozen=True)
class Link:
    id: str  # "L1", "L2", ...: numbered within the graph, then again within each ring
    entity: str
    identifier: str
    strong: bool
    seen_at: datetime | None = None  # when the link was first observed, where Atrium knows


@dataclass
class Graph:
    entities: dict[str, Entity] = field(default_factory=dict)
    identifiers: dict[str, Identifier] = field(default_factory=dict)
    links: list[Link] = field(default_factory=list)


@dataclass
class Ring:
    id: str  # 12 hex of sha256 of the sorted member ids
    members: list[str]
    identifiers: list[str]
    links: list[Link]
    score: int
    stages: list[str]  # "lead", "client"
    strongest: str  # the strongest shared identifier's label
    created_span_hours: float
    strongest_kind: str = ""
    strongest_members: list[str] = field(default_factory=list)


def ring_id(members) -> str:
    return hashlib.sha256("|".join(sorted(members)).encode()).hexdigest()[:12]


def _kind_rank(kind: str) -> int:
    return KIND_ORDER.index(kind) if kind in KIND_ORDER else len(KIND_ORDER)


def _span_hours(members, graph: Graph) -> float:
    moments = [aware(graph.entities[m].created_at) for m in members]
    return round((max(moments) - min(moments)).total_seconds() / 3600, 2) if moments else 0.0


def _stages(members, graph: Graph) -> list[str]:
    kinds = {graph.entities[m].kind for m in members}
    return [stage for stage in ("lead", "client") if stage in kinds]


def ring_score(ring_members, ring_identifiers, ring_links, graph: Graph) -> int:
    """min(100, 15 per member after the first + 12 per strong shared identifier + 15 per flagged member
    + 10 when every member was created within 48 hours + 15 when the ring spans leads and clients)."""
    members = list(ring_members)
    strong = [i for i in ring_identifiers if graph.identifiers[i].kind in STRONG]
    flagged = sum(graph.entities[m].flagged for m in members)
    score = 15 * (len(members) - 1) + 12 * len(strong) + 15 * flagged
    score += 10 if _span_hours(members, graph) <= RECENT_HOURS else 0
    score += 15 if _stages(members, graph) == ["lead", "client"] else 0
    return min(100, score)


class _Components:
    def __init__(self, items):
        self.parent = {i: i for i in items}

    def find(self, i: str) -> str:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def detect_rings(graph: Graph) -> list[Ring]:
    """Connected components of two or more entities over strong, non-hub identifiers, sorted by score, then size."""
    users: dict[str, set[str]] = defaultdict(set)
    for link in graph.links:
        if link.entity in graph.entities and link.identifier in graph.identifiers:
            users[link.identifier].add(link.entity)
    usable = {i: ents for i, ents in users.items() if len(ents) <= HUB_LIMIT}
    parts = _Components(graph.entities)
    for i, ents in usable.items():
        if graph.identifiers[i].kind in STRONG and len(ents) >= 2:
            first, *rest = sorted(ents)
            for other in rest:
                parts.union(first, other)
    groups: dict[str, list[str]] = defaultdict(list)
    for e in graph.entities:
        groups[parts.find(e)].append(e)

    out: list[Ring] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        members = sorted(members)
        inside = set(members)
        shared = {i: ents & inside for i, ents in usable.items() if len(ents & inside) >= 2}
        # Strong before weak, then the identifier most members share; the first strong one is the ring's strongest.
        idents = sorted(shared, key=lambda i: (graph.identifiers[i].kind not in STRONG, -len(shared[i]),
                                               _kind_rank(graph.identifiers[i].kind), graph.identifiers[i].label, i))
        seen: set[tuple[str, str]] = set()
        chosen = []
        for link in graph.links:
            if link.identifier in shared and link.entity in inside and (link.entity, link.identifier) not in seen:
                seen.add((link.entity, link.identifier))
                chosen.append(link)
        chosen.sort(key=lambda link: (not link.strong, idents.index(link.identifier),
                                      graph.entities[link.entity].label, link.entity))
        links = [replace(link, id=f"L{n}") for n, link in enumerate(chosen, start=1)]
        strong = [i for i in idents if graph.identifiers[i].kind in STRONG]
        best = strong[0] if strong else idents[0]
        out.append(Ring(id=ring_id(members), members=members, identifiers=idents, links=links,
                        score=ring_score(members, idents, links, graph), stages=_stages(members, graph),
                        strongest=graph.identifiers[best].label, created_span_hours=_span_hours(members, graph),
                        strongest_kind=graph.identifiers[best].kind, strongest_members=sorted(shared[best])))
    out.sort(key=lambda r: (-r.score, -len(r.members), r.id))
    return out


# ---- The graph from the database -----------------------------------------------------------------------------------

def _digest(kind: str, value: str) -> str:
    """A keyed hash, so an id on the page cannot be reversed by hashing candidate phone numbers or emails."""
    key = get_settings().blind_index_key.encode()
    return f"{kind}:{hmac.new(key, f'{kind}|{value}'.encode(), hashlib.sha256).hexdigest()[:16]}"


def _first_lower(text: str) -> str:
    return text[:1].lower() + text[1:]


def _lead_flags(lead: Lead) -> tuple[bool, tuple[str, ...]]:
    flags: list[str] = []
    if lead.trust_band == "blocked":
        flags.append("Trust: blocked")
    elif lead.trust_band == "high_risk":
        flags.append("Trust: high risk")
    for signal in lead.trust_signals or []:
        if int(signal.get("weight", 0)) <= STRONG_TRUST_WEIGHT or signal.get("blocking"):
            flags.append(f"Trust: {_first_lower(signal['label'])}")
    return lead.trust_band in ("high_risk", "blocked"), tuple(dict.fromkeys(flags))


class _Builder:
    def __init__(self):
        self.graph = Graph()
        self._pairs: set[tuple[str, str]] = set()

    def identifier(self, kind: str, value: str | None, label: str) -> str | None:
        if not value:
            return None
        key = _digest(kind, value)
        self.graph.identifiers.setdefault(key, Identifier(key, kind, label))
        return key

    def link(self, entity: str, identifier: str | None, seen_at: datetime | None) -> None:
        if identifier is None or (entity, identifier) in self._pairs:
            return
        self._pairs.add((entity, identifier))
        kind = self.graph.identifiers[identifier].kind
        self.graph.links.append(Link(f"L{len(self.graph.links) + 1}", entity, identifier, kind in STRONG,
                                     aware(seen_at) if seen_at else None))

    def contact(self, entity: str, email: str | None, phone: str | None, seen_at: datetime | None) -> None:
        email = (email or "").strip().lower()
        if "@" in email:
            self.link(entity, self.identifier("email", email, f"Email at {email.rsplit('@', 1)[1]}"), seen_at)
        digits = "".join(ch for ch in phone or "" if ch.isdigit())
        if digits:
            self.link(entity, self.identifier("phone", digits, f"Phone ending {digits[-4:]}"), seen_at)


def _device_label(raw: str) -> str:
    return f"Device {raw[:4]}…{raw[-4:]}" if len(raw) > 10 else f"Device {raw}"


def _documents(db: Session) -> dict[str, list[IdentityCheck]]:
    out: dict[str, list[IdentityCheck]] = defaultdict(list)
    for check in db.scalars(select(IdentityCheck).order_by(IdentityCheck.created_at)).all():
        out[check.lead_id].append(check)
    return out


def build_graph(db: Session) -> Graph:
    db.flush()  # sessions do not autoflush: rows the caller just added must be part of the graph
    b = _Builder()
    people = {p.id: p for p in db.scalars(select(Person)).all()}
    accounts: dict[str, list[Account]] = defaultdict(list)
    for account in db.scalars(select(Account).order_by(Account.opened_on, Account.number)).all():
        accounts[account.person_id].append(account)
    converted = {c.lead_id: c.person_id for c in db.scalars(select(LeadConversion)).all()}
    all_leads = db.scalars(select(Lead).order_by(Lead.created_at)).all()
    for lead in all_leads:
        if lead.converted_person_id and lead.id not in converted:
            converted[lead.id] = lead.converted_person_id
    alerts: dict[str, list[AmlAlert]] = defaultdict(list)
    for alert in db.scalars(select(AmlAlert).where(AmlAlert.state.in_(OPEN_ALERT_STATES),
                                                   AmlAlert.scenario != RING_SCENARIO)
                            .order_by(AmlAlert.created_at)).all():
        alerts[alert.person_id].append(alert)

    # Clients first, so each entity exists before the converted leads' identifiers attach to it.
    client_ids = {pid for pid in accounts} | {pid for pid in converted.values() if pid in people}
    lead_of = defaultdict(list)
    for lead in all_leads:
        if lead.id in converted and converted[lead.id] in client_ids:
            lead_of[converted[lead.id]].append(lead)
    for pid in sorted(client_ids):
        person = people[pid]
        moments = [aware(person.created_at)]
        moments += [datetime.combine(a.opened_on, time(), tzinfo=timezone.utc) for a in accounts.get(pid, [])]
        moments += [aware(lead.created_at) for lead in lead_of[pid]]
        flags = [f"AML: {_first_lower(a.title)}" for a in alerts.get(pid, [])]
        flagged = bool(flags)
        for lead in lead_of[pid]:
            lead_flagged, lead_flags = _lead_flags(lead)
            flagged, flags = flagged or lead_flagged, flags + list(lead_flags)
        b.graph.entities[f"person:{pid}"] = Entity(f"person:{pid}", "client", person.full_name, min(moments), flagged,
                                                   tuple(dict.fromkeys(flags)))

    documents = _documents(db)
    for lead in all_leads:  # leads before account devices, so a device seen on a lead carries its readable label
        owner = converted.get(lead.id)
        if owner in client_ids:
            entity = f"person:{owner}"
        else:
            entity = f"lead:{lead.id}"
            flagged, flags = _lead_flags(lead)
            b.graph.entities[entity] = Entity(entity, "lead", lead.full_name, aware(lead.created_at), flagged, flags)
        seen = aware(lead.created_at)
        b.contact(entity, lead.email, lead.phone, seen)
        raw = (lead.device_id or "").strip()
        if raw:
            b.link(entity, b.identifier("device", device_hash(raw), _device_label(raw)), seen)
        if lead.ip_hash:  # already a hash of the address; the label shows a few characters of Atrium's own key
            b.link(entity, b.identifier("ip", lead.ip_hash, f"Network …{_digest('ip', lead.ip_hash)[-4:]}"), seen)
        for check in documents.get(lead.id, []):
            number = ((check.extracted or {}).get("document_number") or "").strip().upper()
            if number:
                kind = DOCUMENT_TYPES.get((check.extracted or {}).get("document_type"), "other")
                b.link(entity, b.identifier("document", blind_index(number), f"Identity document ({kind})"),
                       aware(check.created_at))

    devices: dict[str, list[AccountDevice]] = defaultdict(list)
    for device in db.scalars(select(AccountDevice).order_by(AccountDevice.first_seen)).all():
        devices[device.account_id].append(device)
    for pid in sorted(client_ids):
        entity, person = f"person:{pid}", people[pid]
        b.contact(entity, person.email, None, aware(person.created_at))
        for account in accounts.get(pid, []):
            opened = datetime.combine(account.opened_on, time(), tzinfo=timezone.utc)
            if account.bank_index:
                b.link(entity, b.identifier("bank", account.bank_index,
                                            f"Bank account ending {account.bank_last4 or '????'}"), opened)
            for device in devices.get(account.id, []):
                label = f"Device …{device.device_hash[-4:]}" + (f" ({device.label})" if device.label else "")
                b.link(entity, b.identifier("device", device.device_hash, label), device.first_seen)
    return b.graph


def rings(db: Session) -> list[Ring]:
    return detect_rings(build_graph(db))


def ring_by_id(db: Session, ring_id_: str) -> Ring | None:
    return next((r for r in rings(db) if r.id == ring_id_), None)
