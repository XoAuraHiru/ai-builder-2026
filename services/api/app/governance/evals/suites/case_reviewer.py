"""Case review: the deterministic checkers catch every planted fault in a recorded review (free); Gemini Pro's reviews
of five golden alerts, and Flash's as a challenger (live)."""
import hashlib
from datetime import date, datetime, time, timezone
from decimal import Decimal

from app.ai.figures import collect_figures
from app.governance import golden
from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, every_case, rate, run_case, scratch_db, share_passing, suite
from app.models import Account, AmlAlert, BankStatement, Instruction, Person, ReconMatch, StatementLine
from app.services.compliance_ai import check_review, review_alert

REVIEW_BAR = 0.8


@suite("case_reviewer")
def checkers_catch_faults(ctx: EvalContext) -> SuiteResult:
    data = golden.load("case_reviewer/recorded")
    facts = data["facts"]
    evidence_ids = {e["id"] for e in facts["evidence"]}
    figures, names = collect_figures(facts), set(data["names"])
    cases = []
    for c in data["cases"]:
        def check(c=c):
            found = check_review(c["review"], evidence_ids, figures, names)
            return CaseResult(c["id"], "pass" if found == c["expect"] else "fail", expected=c["expect"], actual=found,
                              detail=c["why"])
        cases.append(run_case(c["id"], check))
    return every_case("case_reviewer", "golden", "free", cases,
                      bar="The clean review passes, and every planted fault (a false citation, an invented figure, a "
                          "person not in the inputs) is caught")


def _person(db, full_name: str, country: str, number: str, bank_index: str | None = None,
            bank_last4: str | None = None) -> Account:
    person = Person(kind="investor", full_name=full_name, country=country,
                    email=f"{full_name.lower().replace(' ', '.')}@example.test")
    db.add(person)
    db.flush()
    account = Account(person_id=person.id, number=number, opened_on=date(2025, 1, 2), bank_index=bank_index,
                      bank_last4=bank_last4)
    db.add(account)
    db.flush()
    return account


def build_alert(db, c: dict) -> AmlAlert:
    """The alert with the rows its linked entities read: a shared bank account, or a payer matched to a subscription."""
    linked = c.get("linked")
    bank_index = hashlib.sha256(c["id"].encode()).hexdigest() if linked else None
    p = c["person"]
    account = _person(db, p["full_name"], p.get("country", "US"), p["account"], bank_index,
                      linked.get("bank_last4") if linked else None)
    if linked:
        _person(db, linked["full_name"], linked.get("country", "US"), linked["account"], bank_index,
                linked.get("bank_last4"))
    payer = c.get("payer")
    if payer:
        row = next(e for e in c["evidence"] if e["id"] == payer["instruction"])
        line_row = next(e for e in c["evidence"] if e["id"] == payer["line"])
        day = date.fromisoformat(row["date"])
        db.add(Instruction(id=payer["instruction"], account_id=account.id, fund_code="ATR-BAL", type="subscribe",
                           amount=Decimal(row["amount"]), state="accepted",
                           requested_at=datetime.combine(day, time(15), tzinfo=timezone.utc)))
        ops = Person(kind="ops", full_name="Golden Operations", email=f"golden.ops.{c['id']}@example.test")
        db.add(ops)
        db.flush()
        statement = BankStatement(filename="golden.csv", mime_type="text/csv", sha256="2" * 64, size_bytes=1,
                                  source="csv", uploaded_by=ops.id, notes=[])
        db.add(statement)
        db.flush()
        db.add(StatementLine(id=payer["line"], statement_id=statement.id, line_no=1,
                             value_date=date.fromisoformat(line_row["date"]), amount=Decimal(line_row["amount"]),
                             description=payer["description"], remitter=payer["remitter"], state="matched"))
        db.flush()
        db.add(ReconMatch(line_ids=[payer["line"]], instruction_ids=[payer["instruction"]], tier="unique_amount",
                          confidence=0.85, evidence=[], proposed_by="rules", state="accepted"))
    a = c["alert"]
    alert = AmlAlert(scenario=a["scenario"], title=a["title"], severity=a["severity"], score=a["score"],
                     person_id=account.person_id, account_id=account.id, summary=a["summary"], evidence=c["evidence"],
                     fingerprint=hashlib.sha256(f"golden|{c['id']}".encode()).hexdigest(), state="open")
    db.add(alert)
    db.flush()
    return alert


def grade_review(c: dict, review: dict) -> CaseResult:
    narrative = " ".join(p["text"] for p in review["narrative"]).strip()
    expect = c["expect"]
    actual = {"triage": review["triage"], "dropped_citations": review["dropped_citations"],
              "unsupported_figures": review["unsupported_figures"], "unknown_names": review.get("unknown_names", [])}
    if not narrative:
        return CaseResult(c["id"], "fail", expected=expect, actual=actual, detail="The review has no narrative.")
    problems = []
    if review["triage"] not in expect["triage_in"]:
        problems.append(f"triage {review['triage']}, expected {' or '.join(expect['triage_in'])}")
    if review["dropped_citations"]:
        problems.append(f"cited rows not in the evidence ({', '.join(review['dropped_citations'])})")
    if review["unsupported_figures"]:
        problems.append(f"figures not in the inputs ({', '.join(review['unsupported_figures'])})")
    if actual["unknown_names"]:
        problems.append(f"named people not in the inputs ({', '.join(actual['unknown_names'])})")
    missing = [f for f in expect["facts"] if f.lower() not in narrative.lower()]
    if missing:
        problems.append(f"the narrative leaves out {', '.join(missing)}")
    detail = c["why"] if not problems else f"{'; '.join(problems).capitalize()}. {c['why']}"
    return CaseResult(c["id"], "fail" if problems else "pass", expected=expect, actual=actual, detail=detail)


def review_cases(llm) -> list[CaseResult]:
    cases = []
    for c in golden.load("case_reviewer/alerts")["cases"]:
        with scratch_db() as db:
            alert = build_alert(db, c)
            cases.append(run_case(c["id"], lambda c=c, db=db, alert=alert: grade_review(c, review_alert(db, llm, alert)),
                                  db=db))
    return cases


@suite("case_reviewer", tier="live")
def golden_alerts(ctx: EvalContext) -> SuiteResult:
    cases = review_cases(ctx.llm)
    passed = sum(c.outcome == "pass" for c in cases)
    return rate("case_reviewer", "golden", "live", cases,
                bar=f"At least {REVIEW_BAR:.0%} of five golden alerts reviewed right: triage, citations, figures, "
                    "people and the required facts",
                metric=f"{passed} of {len(cases)} alerts reviewed right on Pro", value=share_passing(cases),
                threshold=REVIEW_BAR)


class FlashOnly:
    """The same calls with Pro switched off: the challenger runs the reviews on Flash."""

    def __init__(self, llm):
        self.llm = llm

    def generate_json(self, **kwargs):
        return self.llm.generate_json(**{**kwargs, "pro": False})


@suite("case_reviewer", kind="challenger", tier="live")
def flash_challenger(ctx: EvalContext) -> SuiteResult:
    cases = review_cases(FlashOnly(ctx.llm))
    judged = [c for c in cases if c.outcome != "error"]
    triage = sum(1 for c in judged if c.actual and c.actual["triage"] in c.expected["triage_in"])
    citations = sum(1 for c in judged if c.actual and not c.actual["dropped_citations"])
    figures = sum(1 for c in judged if c.actual and not c.actual["unsupported_figures"])
    cost = sum(c.cost_usd for c in cases)
    latency = sum(c.latency_ms for c in judged) // max(1, len(judged))
    passed = sum(c.outcome == "pass" for c in cases)
    return rate("case_reviewer", "challenger", "live", cases,
                bar="Evidence for promotion only: the same five alerts on Flash, compared with Pro",
                metric=(f"Flash: {passed} of {len(cases)} right; triage {triage}, clean citations {citations}, "
                        f"clean figures {figures} of {len(judged)}; ${cost:.4f}, {latency} ms a review"),
                value=share_passing(cases), threshold=REVIEW_BAR)
