"""Reconciliation: golden scenarios through the rules and the scorer (free) and through the ADK agent (live)."""
import hashlib
from datetime import date, datetime, time, timezone
from decimal import Decimal

from app.governance import golden
from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, rate, scratch_db, suite
from app.models import Account, BankStatement, Instruction, Person, StatementLine
from app.seed.funds import seed_funds
from app.services import reconciliation
from app.services.reconciliation import busy_instruction_ids, open_receipts, propose_by_rules, unmatched_deposits

PRECISION_BAR_RULES, PRECISION_BAR_SCORER = 1.0, 0.8


def _instruction_id(scenario: str, receipt: dict) -> str:
    """An id whose first eight characters are the receipt's reference code, so payment_reference gives it back."""
    code = receipt["reference"].split("-", 1)[1].lower()
    pad = hashlib.sha256(f"{scenario}|{receipt['id']}".encode()).hexdigest()
    return (code + pad)[:32]


def build_scenario(db, scenario: dict) -> dict[str, str]:
    """Create the scenario's people, accounts, accepted subscriptions, statement and lines; return golden id -> row id."""
    seed_funds(db)
    ids: dict[str, str] = {}
    accounts: dict[str, Account] = {}
    for r in scenario["receipts"]:
        account = accounts.get(r["account"])
        if account is None:
            email = f"{r['holder'].lower().replace(' ', '.')}.{r['account'].lower()}@example.test"
            person = Person(kind="investor", full_name=r["holder"], email=email)
            db.add(person)
            db.flush()
            account = Account(person_id=person.id, number=r["account"], opened_on=date(2025, 1, 2))
            db.add(account)
            db.flush()
            accounts[r["account"]] = account
        requested = datetime.combine(date.fromisoformat(r["requested_on"]), time(15), tzinfo=timezone.utc)
        row = Instruction(id=_instruction_id(scenario["id"], r), account_id=account.id, fund_code=r["fund"],
                          type="subscribe", amount=Decimal(r["amount"]), state="accepted", requested_at=requested)
        db.add(row)
        db.flush()
        ids[r["id"]] = row.id
    ops = Person(kind="ops", full_name="Golden Operations", email="golden.recon@example.test")
    db.add(ops)
    db.flush()
    statement = BankStatement(filename=f"{scenario['id']}.csv", mime_type="text/csv",
                              sha256=hashlib.sha256(scenario["id"].encode()).hexdigest(), size_bytes=1, source="csv",
                              uploaded_by=ops.id, notes=[])
    db.add(statement)
    db.flush()
    for n, x in enumerate(scenario["lines"], start=1):
        line = StatementLine(statement_id=statement.id, line_no=n, value_date=date.fromisoformat(x["date"]),
                             amount=Decimal(x["amount"]), description=x["description"], remitter=x.get("remitter"),
                             reference=x.get("reference"), channel=x.get("channel"), state="unmatched")
        db.add(line)
        db.flush()
        ids[x["id"]] = line.id
    db.flush()
    return ids


def pairs_of(proposals, ids: dict[str, str]) -> set[tuple[frozenset[str], frozenset[str]]]:
    """Proposals (ReconMatch rows or the scorer's dicts) as (line ids, instruction ids) in golden ids."""
    back = {v: k for k, v in ids.items()}
    out = set()
    for p in proposals:
        if isinstance(p, dict):
            line_ids = p["line_ids"]
            instruction_ids = p.get("instruction_ids") or [p["instruction_id"]]
        else:
            line_ids, instruction_ids = p.line_ids, p.instruction_ids
        out.add((frozenset(back.get(i, i) for i in line_ids), frozenset(back.get(i, i) for i in instruction_ids)))
    return out


def truth_of(scenario: dict) -> set[tuple[frozenset[str], frozenset[str]]]:
    return {(frozenset(t["lines"]), frozenset(t["receipts"])) for t in scenario["truth"]}


def precision_recall(proposed: set, truth: set) -> tuple[float | None, float | None]:
    precision = len(proposed & truth) / len(proposed) if proposed else None
    recall = len(proposed & truth) / len(truth) if truth else None
    return precision, recall


def decoy_hit(scenario: dict, proposed: set) -> bool:
    decoys = set(scenario.get("decoys", []))
    return any(decoys & set(lines) for lines, _ in proposed)


def scorer_proposals(db) -> list[dict]:
    """What the scorer proposes on what the rules left, exactly as the agent's fallback would."""
    db.flush()
    busy = busy_instruction_ids(db)
    receipts = [r for r in open_receipts(db) if r.instruction_id not in busy]
    return reconciliation.fallback_proposals(unmatched_deposits(db), receipts)


def _show(pair) -> list:
    lines, receipts = pair
    return [sorted(lines), sorted(receipts)]


@suite("reconciler_agent")
def rules_and_scorer(ctx: EvalContext) -> SuiteResult:
    cases = []
    rules_hits = rules_all = scorer_hits = scorer_all = found = truth_total = 0
    for s in golden.load("reconciler_agent/scenarios")["cases"]:
        with scratch_db() as db:
            ids = build_scenario(db, s)
            by_rules = pairs_of(propose_by_rules(db), ids)
            by_scorer = pairs_of(scorer_proposals(db), ids)
        truth = truth_of(s)
        hit_decoy = decoy_hit(s, by_rules | by_scorer)
        rules_hits += len(by_rules & truth)
        rules_all += len(by_rules)
        scorer_hits += len(by_scorer & truth)
        scorer_all += len(by_scorer)
        found += len((by_rules | by_scorer) & truth)
        truth_total += len(truth)
        ok = by_rules <= truth and not hit_decoy
        detail = s["why"] if ok else (("A decoy line was proposed. " if hit_decoy else "The rules proposed a wrong "
                                       "match. ") + s["why"])
        cases.append(CaseResult(s["id"], "pass" if ok else "fail", expected=sorted(map(_show, truth)),
                                actual={"rules": sorted(map(_show, by_rules)), "scorer": sorted(map(_show, by_scorer))},
                                detail=detail))
    rules_p = rules_hits / rules_all if rules_all else 1.0
    scorer_p = scorer_hits / scorer_all if scorer_all else 1.0
    recall = found / truth_total if truth_total else 1.0
    bars_met = rules_p >= PRECISION_BAR_RULES and scorer_p >= PRECISION_BAR_SCORER
    return rate("reconciler_agent", "golden", "free", cases,
                bar="Rules 100% precise, scorer at least 80% precise, no proposal on a decoy",
                metric=f"Rules precision {rules_p:.0%}, scorer precision {scorer_p:.0%}, recall {recall:.0%}",
                value=1.0 if bars_met and all(c.outcome == "pass" for c in cases) else 0.0, threshold=1.0)
