"""AML scenarios: each fires on its golden case and stays quiet on its near miss."""
import hashlib
from datetime import date, datetime, time, timezone
from decimal import Decimal

from app.governance import golden
from app.governance.evals.framework import (CaseResult, EvalContext, SuiteResult, every_case, rate, run_case, scratch_db,
                                            suite)
from app.models import Account, BankStatement, Instruction, Person, ReconMatch, StatementLine
from app.seed.funds import seed_funds
from app.services import aml
from app.services.ledger import apply_posting

SCENARIOS = {"structuring": aml.structuring, "rapid_in_out": aml.rapid_in_out,
             "third_party_funding": aml.third_party_funding, "linked_round_trip": aml.linked_round_trip,
             "velocity": aml.velocity, "dormant_reactivation": aml.dormant_reactivation,
             "high_risk_jurisdiction": aml.high_risk_jurisdiction}
DEFAULT_HOUR = 15  # 15:00 UTC is 11:00 in New York, so the day is the same in both


def _moment(day: str, hour: int = DEFAULT_HOUR) -> datetime:
    return datetime.combine(date.fromisoformat(day), time(hour), tzinfo=timezone.utc)


def build(db, case: dict) -> None:
    """Create exactly the rows the case lists (people, accounts, instructions, postings, bank links, statement lines
    and matches), through the models and the ledger, then flush."""
    seed_funds(db)
    accounts: dict[str, Account] = {}
    for a in case.get("accounts", []):
        person = Person(kind="investor", full_name=a["full_name"], email=a["email"], country=a.get("country", "US"))
        db.add(person)
        db.flush()
        account = Account(person_id=person.id, number=a["number"], opened_on=date.fromisoformat(a["opened_on"]))
        db.add(account)
        db.flush()
        accounts[a["number"]] = account
    for link in case.get("bank_links", []):
        index = hashlib.sha256("|".join(link["accounts"]).encode()).hexdigest()
        for number in link["accounts"]:
            accounts[number].bank_index, accounts[number].bank_last4 = index, link.get("last4")
    instructions: dict[str, Instruction] = {}
    for k, i in enumerate(case.get("instructions", [])):
        row = Instruction(account_id=accounts[i["account"]].id, fund_code=i["fund"], type=i["type"],
                          amount=Decimal(i["amount"]) if i.get("amount") is not None else None,
                          units=Decimal(i["units"]) if i.get("units") is not None else None,
                          state=i.get("state", "accepted"), requested_at=_moment(i["day"], i.get("hour", DEFAULT_HOUR)))
        db.add(row)
        db.flush()
        instructions[i.get("id", f"i{k}")] = row
    for p in case.get("postings", []):
        amount = Decimal(p["amount"])
        sign = 1 if p["type"] == "subscription" else -1
        apply_posting(db, account_id=accounts[p["account"]].id, instrument=p["fund"], instrument_type="fund",
                      posting_type=p["type"], units=sign * amount, cash=-sign * amount, price=Decimal("1"),
                      value_date=date.fromisoformat(p["day"]), reference=f"golden-{p['type']}-{p['day']}")
    lines: dict[str, StatementLine] = {}
    if case.get("statement_lines"):
        uploader = Person(kind="ops", full_name="Golden Uploader", email="golden.ops@example.test")
        db.add(uploader)
        db.flush()
        statement = BankStatement(filename="golden.csv", mime_type="text/csv", sha256="0" * 64, size_bytes=1,
                                  source="csv", uploaded_by=uploader.id, notes=[])
        db.add(statement)
        db.flush()
        for n, x in enumerate(case["statement_lines"], start=1):
            line = StatementLine(statement_id=statement.id, line_no=n, value_date=date.fromisoformat(x["day"]),
                                 amount=Decimal(x["amount"]), description=x["description"], remitter=x.get("remitter"),
                                 reference=x.get("reference"), state=x.get("state", "matched"))
            db.add(line)
            db.flush()
            lines[x["id"]] = line
    for m in case.get("matches", []):
        db.add(ReconMatch(line_ids=[lines[i].id for i in m["lines"]],
                          instruction_ids=[instructions[i].id for i in m["instructions"]],
                          tier=m.get("tier", "unique_amount"), confidence=0.85, evidence=[], proposed_by="rules",
                          state=m.get("state", "accepted")))
    db.flush()


@suite("aml_scenarios")
def positives_and_near_misses(ctx: EvalContext) -> SuiteResult:
    cases = []
    for c in golden.load("aml_scenarios/cases")["cases"]:
        def check(c=c):
            with scratch_db() as db:
                build(db, c)
                findings = SCENARIOS[c["scenario"]](db, date.fromisoformat(c["today"]))
            fired = bool(findings)
            return CaseResult(c["id"], "pass" if fired == c["expect_fires"] else "fail",
                              expected={"fires": c["expect_fires"]}, actual={"fires": fired, "findings": len(findings)},
                              detail=c["why"])
        cases.append(run_case(c["id"], check))
    return every_case("aml_scenarios", "golden", "free", cases,
                      bar="Every scenario fires on its case and stays quiet on its near miss")


MUTATION_BAR = 0.8
MUTATION_DAY = date(2026, 10, 12)


@suite("aml_scenarios", kind="red_team", tier="live")
def fraud_mutations(ctx: EvalContext) -> SuiteResult:
    """Structuring at fresh amounts under $10,000, generated from a fixed seed: three subscriptions within five days
    must raise the structuring scenario whatever the amounts."""
    from datetime import timedelta

    from app.governance.redteam import FRAUD_MUTATIONS

    cases = []
    for m in (m for m in FRAUD_MUTATIONS if m["kind"] == "structuring_amount"):
        def check(m=m):
            case = {"accounts": [{"number": "ACC-0501", "full_name": "Mutation Client", "email": "mutation@example.test",
                                  "country": "US", "opened_on": "2025-01-02"}],
                    "instructions": [{"account": "ACC-0501", "type": "subscribe", "fund": "ATR-BAL", "amount": str(a),
                                      "day": (MUTATION_DAY - timedelta(days=6 - 2 * k)).isoformat(),
                                      "state": "accepted"} for k, a in enumerate(m["amounts"])]}
            with scratch_db() as db:
                build(db, case)
                findings = aml.structuring(db, MUTATION_DAY)
            caught = bool(findings)
            return CaseResult(m["id"], "pass" if caught else "fail", expected="caught",
                              actual={"attack": m["kind"], "output": {"amounts": m["amounts"], "alerts": len(findings)}},
                              detail=m["why"] + (" Caught." if caught else " Missed."))
        cases.append(run_case(m["id"], check))
    caught = sum(c.outcome == "pass" for c in cases)
    return rate("aml_scenarios", "red_team", "live", cases,
                bar=f"At least {MUTATION_BAR:.0%} of structuring mutations caught",
                metric=f"{caught} of {len(cases)} mutations caught", value=caught / len(cases) if cases else None,
                threshold=MUTATION_BAR)
