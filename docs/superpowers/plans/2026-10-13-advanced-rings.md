# Fraud Ring Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One graph across the whole lifecycle (leads, clients, devices, bank accounts, documents) that finds fraud rings no single team can see, explained by Gemini, with a case or a trust flag only on a person's action.

**Architecture:** `app/services/rings.py` builds an identifier graph from the database, finds connected components over strong links (with weak IP links and hub damping), scores them, and narrates one on request with citations restricted to link ids. Routes live in `app/routers/rings.py` under `/compliance`; the page is `/compliance/rings`, reusing and extending `EntityGraph`.

**Tech Stack:** as the master plan.

**Spec:** `docs/superpowers/specs/2026-10-13-atrium-advanced-design.md` §6. **Master plan:** `docs/superpowers/plans/2026-10-13-atrium-advanced.md`.

**Branch:** `feat/adv-rings` in its own worktree, from the Phase F head of `feat/advanced`.

## Global Constraints

All of the master plan's. In addition:
- Do not edit `nav.ts`, `journeys.ts`, their tests, `app/page.tsx`, `README.md` or the plans index.
- The model key is `ring_narrator`; its inventory source is `module:app.services.rings`, so the service module must have exactly that path.
- Raw identity document numbers, phone numbers and email addresses are never sent to the page or to Gemini; nodes carry labels such as "Phone ending 0123", "Email at mailtemp.click", "Device dev-…0001", "Bank account ending 4471", "Identity document (passport)".
- `AmlAlert.person_id` is required: "Open a case" is offered only for rings with at least one client; a ring of leads only offers "Flag the leads".

## Review Focus

1. A shared office network (one IP hash used by many genuine leads): no ring forms through it. Pinned in R1 (hub damping and weak links).
2. Two leads sharing only an IP hash and nothing else: no ring. Pinned in R1.
3. A ring that changes between viewing and acting: the action re-reads the ring by id and returns 409 "This ring has changed; reload it." Pinned in R3.
4. Flagging the same ring's leads twice: idempotent, one T09 per lead. Pinned in R3.
5. A narrative citing a link id that is not in the ring: dropped and counted, never shown as evidence. Pinned in R2.

## File Structure

- Create: `services/api/app/services/rings.py`, `services/api/app/models/rings.py` (`RingFlag`), `services/api/app/governance/evals/suites/ring_narrator.py`, `services/api/app/governance/golden/ring_narrator/{graph,rings}.json`
- Modify: `services/api/app/models/__init__.py` (register `RingFlag`), `services/api/app/services/trust.py` (T09), `services/api/app/seed/rings.py` (replace the stub), `services/api/app/routers/rings.py` (replace the stub)
- Modify: `apps/web/src/lib/compliance.ts` (graph node kinds; the `ring` scenario copy), `apps/web/src/components/entity-graph.tsx` (new kinds, dashed weak edges)
- Create: `apps/web/src/lib/rings.ts`, `rings.test.ts`, `apps/web/src/app/compliance/rings/page.tsx`
- Tests: `services/api/tests/test_rings.py`, `services/api/tests/test_rings_api.py`

---

### Task R1: The graph and ring detection (pure, then from the database)

**Interfaces:**
- Produces:

```python
STRONG = ("bank", "device", "document", "phone", "email")
WEAK = ("ip",)
HUB_LIMIT = 8   # an identifier shared by more than this many entities is a hub and is ignored

@dataclass(frozen=True) class Entity: id: str ("lead:<id>" | "person:<id>"); kind: "lead" | "client"; label: str; created_at: datetime; flagged: bool; flags: tuple[str, ...]
@dataclass(frozen=True) class Identifier: id: str ("<kind>:<hash>"); kind: str; label: str
@dataclass(frozen=True) class Link: id: str ("L1", "L2", ...); entity: str; identifier: str; strong: bool
@dataclass Graph: entities: dict[str, Entity]; identifiers: dict[str, Identifier]; links: list[Link]
@dataclass Ring: id: str (12 hex of sha256 of the sorted member ids); members: list[str]; identifiers: list[str]; links: list[Link]; score: int; stages: list[str] ("lead", "client"); strongest: str (an identifier label); created_span_hours: float

def detect_rings(graph: Graph) -> list[Ring]       # pure; sorted by score, then size
def ring_score(ring_members, ring_identifiers, ring_links, graph) -> int
def build_graph(db) -> Graph
def rings(db) -> list[Ring]                       # detect_rings(build_graph(db))
def ring_by_id(db, ring_id) -> Ring | None
```

Detection: union-find over entities joined by a shared strong identifier (ignoring hubs: identifiers linked to more than `HUB_LIMIT` entities). A weak identifier (IP) joins an entity to a component only when the entity is already linked to that component by a strong identifier, so weak links are shown but never form rings. Components with at least 2 entities are rings; their links are every link between their members and the identifiers two or more members share (strong or weak).

Score (0–100): `min(100, 15 * (members - 1) + 12 * strong_shared_identifiers + 15 * flagged_members + (10 if created_span_hours <= 48 else 0) + (15 if both stages present else 0))`.

`build_graph` identifiers:
- Lead: `email` (lower-cased), `phone` (digits only), `device_id` hashed with `device_hash` (`app/services/devices.py`, the same hash accounts use), `ip_hash` (weak), and each identity check's `extracted["document_number"]` through `blind_index` (`app/services/blind_index.py`).
- Client (a `Person` with an `Account`): `Person.email`, `Account.bank_index`, each `AccountDevice.device_hash`.
- A converted lead (`LeadConversion`) and its person are one entity (the client), so a client is not linked to its own lead.
- Identifier ids hash the normalised value (`sha256(...)[:16]`), never the raw value; labels follow the Global Constraints.
- `flagged`: a lead with trust band `high_risk` or blocked, or a client with an open or escalated AML alert; `flags` lists why ("Trust: high risk", "AML: money in and straight out").

- [ ] **Step 1: Failing tests** (`tests/test_rings.py`), pure first, on a hand-built `Graph`:
  - three leads sharing one device form one ring with score as computed by the formula in the test by hand;
  - nine leads sharing one IP and nothing else: no ring; two leads sharing only an IP: no ring;
  - a lead and a client sharing a device: one ring spanning both stages, with the +15;
  - an identifier shared by nine entities (a hub) does not join them, but a second strong identifier between two of them still does;
  - the ring id is stable when members are listed in another order.
  - Then from the database with `seed_demo_leads` (and the people and accounts the test makes): the device ring (Jordan, Taylor, Casey, and Alex if they share the device; read `app/seed/leads.py`) is found; M. Chen and Michael Chen are found through the shared phone; no raw email, phone or document number appears in any label or id (assert against the seeded values).
- [ ] **Steps 2–5:** run, implement, run, commit `feat(rings): a whole-lifecycle identifier graph and ring detection`.

### Task R2: The narrative

**Interfaces:**
- Produces:

```python
class RingPart(BaseModel): text: str = Field(max_length=500); links: list[str] = Field(default_factory=list, max_length=8)
class RingNarrative(BaseModel):
    pattern: Literal["synthetic_identity_farm", "mule_network", "account_takeover", "duplicate_identity", "unclear"]
    summary: str = Field(max_length=400)
    parts: list[RingPart] = Field(min_length=1, max_length=5)
    next_checks: list[str] = Field(default_factory=list, max_length=4)
NARRATIVE_PROMPT   # the ring's members (labels, stages, flags) and links (ids, kinds, labels); data, not instructions; cite only the given link ids; never guess intent beyond the evidence
def narrate_ring(db, llm, ring: Ring) -> dict      # {"narrative": RingNarrative, "dropped_citations": int, "model": str}
```

`narrate_ring`: `ensure_closed(db, "ring_narrator")`; one Flash call (purpose `ring_narrative`); record it with `record_decision` (agent `compliance_copilot`, subject type `ring`, subject id the ring id); drop any cited id not in the ring's link ids and count them.

- [ ] **Step 1: Failing tests:** a FakeLLM narrative citing `L1` and `L99` keeps `L1`, drops `L99`, and reports 1 dropped; the breaker open raises `BreakerOpen` with no LLM call; the prompt contains no raw email, phone or document number from the ring's entities.
- [ ] **Steps 2–5:** run, implement, run, commit `feat(rings): Gemini explains a ring, citing only its links`.

### Task R3: Actions, T09, the seed link, the routes

**Interfaces:**
- `RingFlag` (`ring_flag`): `lead_id`, `ring_id`, `flagged_by`, unique (`lead_id`, `ring_id`).
- T09 in `trust.py`: `_ring_signals(db, lead)` → `TrustSignal("T09", "Part of a fraud ring", -25, "Flagged by <name> on <date>", "rings", False)` when a `RingFlag` exists for the lead; included in `assess_trust`.
- `open_case(db, ring, by: Person) -> AmlAlert`: scenario `ring`, severity `high` when score ≥ 70 else `medium`, the person the client member with the most flags (409 "This ring has no client, so there is no one to open a case on; flag the leads instead." when none), the account that person's first account, title "Possible fraud ring of N identities", summary from the ring's strongest identifier, evidence one row per link (`{"kind": "ring_link", "id": link id, "date": ..., "amount": None, "detail": label}`, matching the evidence row shape the alert page reads: check `EvidenceRow` in `apps/web/src/lib/compliance.ts` and add `ring_link` to its kinds). Idempotent per ring id (store the ring id in the alert's evidence or title and refuse a second open case for the same ring with 409 naming the existing alert).
- `flag_leads(db, ring, by) -> int`: a `RingFlag` per lead member not already flagged, then `apply_trust` for each; returns the number newly flagged.
- `seed_ring_link(db)` (replace the stub): when Sofia Rossi's account (`sofia@atrium.demo`) exists and has no device with `device_hash("dev-ring-0001")`, add an `AccountDevice` (label "Chrome on Windows", first seen the day after the ring leads were created, last seen at her money-out day); return True when added. Read `app/seed/leads.py` to confirm the ring's device id.
- Routes (`router = APIRouter(prefix="/compliance", tags=["rings"])`, compliance role as `app/routers/compliance.py` uses):
  - `GET /compliance/rings` → `{"rings": [RingOut], "strongest": RingOut | null}` where `RingOut = {id, score, members: [{id, kind, label, flags}], stages, strongest, identifiers: n, links: n, case_alert_id | null, flagged_leads: n}`
  - `GET /compliance/rings/{ring_id}` → `RingOut` plus `graph: {nodes: [{id, kind, label, flagged}], edges: [{source, target, label, strong, id}]}` (nodes are entities and identifiers; edges are links)
  - `POST /compliance/rings/{ring_id}/narrate`, `/case`, `/flag-leads`; 404 for an unknown ring; 409 when the ring id no longer resolves to the same members (the client sends `members` it saw; compare).

- [ ] **Step 1: Failing tests** (`tests/test_rings_api.py`): with the seeds (`seed_demo_leads`, the operations seed that creates Sofia and her alert: read `tests/test_operations_seed.py` for how it seeds a test database, then `seed_ring_link`), the strongest ring spans leads and a client and includes Sofia; its detail graph has dashed (weak) and solid edges; narrate with a FakeLLM; open a case once (201) and twice (409); a lead-only ring's case is 409 with the "flag the leads instead" text; flag-leads twice flags each lead once and adds T09 to their trust signals; Mei gets 403.
- [ ] **Steps 2–5:** run, implement, run the whole API suite, commit `feat(rings): open a case or flag the leads, and the seeded link that joins a lead ring to a client`.

### Task R4: Suites for `ring_narrator`

- `golden/ring_narrator/graph.json`: a hand-built graph (entities, identifiers, links) with three true rings and two traps (an office IP hub; two leads sharing only an IP); `rings.json` the golden rings (member sets) and, for two of them, the golden `pattern` (`synthetic_identity_farm` for the device ring with throwaway emails; `mule_network` for the ring reaching a client with a money-in-and-out alert).
- Free suite `detection_on_a_golden_graph`: `detect_rings` finds exactly the golden member sets. Bar: exact.
- Live suite `narratives`: narrate the two rings; pass when no citation is dropped and the pattern equals the golden label. Bar: both pass.
- Tests with FakeLLM for the live suite (pass and fail paths) in `tests/test_rings.py`.
- Commit `feat(governance): golden suites for ring detection and narratives`.

### Task R5: The Fraud rings page

**Files:** `apps/web/src/lib/rings.ts`, `rings.test.ts`, `apps/web/src/lib/compliance.ts`, `apps/web/src/components/entity-graph.tsx`, `apps/web/src/app/compliance/rings/page.tsx`.

- [ ] **Step 1: Failing tests** (`rings.test.ts`): `ringHeadline(ring)` for the strongest seeded shape returns "4 identities share one device, and that device also signs in to a client account flagged for money in and straight out." (derive the sentence from members, stages, the strongest identifier's kind and the client's flags; write the function so this exact string results for that input, and a generic "N identities share K identifiers" otherwise); `PATTERN_LABEL` names every pattern ("Synthetic identity farm", "Mule network", "Account takeover", "Duplicate identity", "Unclear"); `stageLabel(["lead", "client"])` is "Leads and clients".
- [ ] **Step 2: Run** to see them fail.
- [ ] **Step 3: Implement**:
  - `compliance.ts`: extend `GraphNode["kind"]` with `"lead" | "client" | "device" | "phone" | "email" | "ip" | "document"` (keep the existing kinds), `GraphEdge` with optional `strong?: boolean` and `id?: string`, `SCENARIO_COPY.ring` ("Several identities share devices, bank accounts or documents across the lifecycle."), `EVIDENCE_KIND.ring_link` ("Ring link").
  - `entity-graph.tsx`: styles for the new kinds (entities as filled discs, identifiers as small squares, flagged in the loss tone), and `strokeDasharray` for `strong === false`. The alert page's graph must look unchanged (it passes no `strong`).
  - `/compliance/rings/page.tsx`: `PageHeader` "Fraud rings" with description "One graph across leads, clients, devices, bank accounts and documents. The graph finds the rings; Gemini only explains them; you decide." A `KeyMoment` (tone `alert`) with `ringHeadline(strongest)` and the actions **Explain this ring**, **Open a case** (hidden for lead-only rings), **Flag the leads**. Then a two-column layout at 2xl (list of rings: score, size, stages, strongest link; selecting one loads its detail), the graph, members with their flags, and links (id, kind, label, strong or weak). The narrative in `AiProse` with each part's link ids as small chips that highlight the matching edge; the dropped-citation count when non-zero; next checks as a list. After an action, reload and show "Case opened" with a link to the alert, or "3 leads flagged; their Trust Scores were updated."
- [ ] **Step 4: Run** `pnpm tsc --noEmit && pnpm lint && pnpm vitest run`; screenshot `/compliance/rings` as `omar@atrium.demo` at 390 and 1440 px against the local servers seeded with `AUTO_SEED=true` (after `seed_ring_link` runs at boot). Check the alert page's graph is unchanged. Fix what looks wrong.
- [ ] **Step 5: Commit** `feat(web): the Fraud rings page: the strongest ring first, its graph, Gemini's reading, and the actions`.
