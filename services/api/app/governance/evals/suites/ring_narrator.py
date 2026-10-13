"""Ring narrative: ring detection on a hand-built golden graph (free), and Gemini's reading of two golden rings (live).

The graph holds three true rings and two traps: an office network and switchboard shared by ten genuine leads (hubs,
which join no one) and two leads in a cafe who share only a network address (a weak link, which never makes a ring).
Printed text stays ASCII so the deploy gate's output survives any console."""
import json
from datetime import datetime
from pathlib import Path

from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, every_case, run_case, scratch_db, suite
from app.services.rings import STRONG, Entity, Graph, Identifier, Link, detect_rings, narrate_ring

GOLDEN = Path(__file__).resolve().parents[2] / "golden" / "ring_narrator"


def load_golden() -> tuple[Graph, dict]:
    raw = json.loads((GOLDEN / "graph.json").read_text(encoding="utf-8"))
    entities = {e["id"]: Entity(e["id"], e["kind"], e["label"], datetime.fromisoformat(e["created_at"]),
                                bool(e["flagged"]), tuple(e["flags"])) for e in raw["entities"]}
    identifiers = {i["id"]: Identifier(i["id"], i["kind"], i["label"]) for i in raw["identifiers"]}
    links = [Link(f"L{n}", entity, identifier, identifiers[identifier].kind in STRONG)
             for n, (entity, identifier) in enumerate(raw["links"], start=1)]
    return Graph(entities, identifiers, links), json.loads((GOLDEN / "rings.json").read_text(encoding="utf-8"))


@suite("ring_narrator")
def detection_on_a_golden_graph(ctx: EvalContext) -> SuiteResult:
    graph, golden = load_golden()
    found = [frozenset(r.members) for r in detect_rings(graph)]
    cases: list[CaseResult] = []
    for ring in golden["rings"]:
        want = frozenset(ring["members"])
        hit = found.count(want) == 1
        cases.append(CaseResult(ring["name"], "pass" if hit else "fail", expected=sorted(want),
                                actual=[sorted(f) for f in found if f & want],
                                detail="Found exactly once." if hit else "Not found as one ring with these members."))
    for trap in golden["traps"]:
        caught = [sorted(f) for f in found if f & set(trap["members"])]
        cases.append(CaseResult(trap["name"], "fail" if caught else "pass", expected=[], actual=caught,
                                detail=trap["why"] if not caught else "A trap's members were joined into a ring."))
    extra = [sorted(f) for f in found if f not in {frozenset(r["members"]) for r in golden["rings"]}]
    cases.append(CaseResult("no_other_rings", "fail" if extra else "pass", expected=[], actual=extra,
                            detail="No ring beyond the golden ones." if not extra else f"{len(extra)} extra ring(s)."))
    return every_case("ring_narrator", "golden", "free", cases,
                      bar="Exactly the golden rings: three found, and the office and cafe networks join no one")


@suite("ring_narrator", tier="live")
def narratives(ctx: EvalContext) -> SuiteResult:
    graph, golden = load_golden()
    found = {frozenset(r.members): r for r in detect_rings(graph)}
    cases: list[CaseResult] = []
    with scratch_db() as db:
        for spec in golden["rings"]:
            if not spec.get("pattern"):
                continue
            ring = found.get(frozenset(spec["members"]))

            def check(spec=spec, ring=ring) -> CaseResult:
                if ring is None:
                    return CaseResult(spec["name"], "fail", expected=spec["pattern"], detail="The ring was not found.")
                out = narrate_ring(db, ctx.llm, ring, graph)
                pattern, dropped = out["narrative"].pattern, out["dropped_citations"]
                ok = pattern == spec["pattern"] and dropped == 0
                return CaseResult(spec["name"], "pass" if ok else "fail",
                                  expected={"pattern": spec["pattern"], "dropped_citations": 0},
                                  actual={"pattern": pattern, "dropped_citations": dropped},
                                  detail=f"Named {pattern}; {dropped} citation{'s' if dropped != 1 else ''} to links "
                                         "outside the ring.")

            cases.append(run_case(spec["name"], check, db=db))
    return every_case("ring_narrator", "golden", "live", cases,
                      bar="Both golden rings: the pattern named matches and every citation is one of the ring's links")
