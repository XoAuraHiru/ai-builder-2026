"""Narration reading (Gemini Flash): twelve golden narrations read in one call, as a statement is, graded on the
remitter and the reference."""
from datetime import date
from decimal import Decimal

from app.governance import golden
from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, ai_cost, rate, scratch_db, share_passing, suite
from app.models import BankStatement, Person
from app.services.statements import RawLine, normalise

NARRATION_BAR = 0.9
STATEMENT_DAY = date(2026, 10, 12)


def _same(a: str | None, b: str | None) -> bool:
    return " ".join((a or "").split()).lower() == " ".join((b or "").split()).lower()


def scratch_statement(db) -> str:
    ops = Person(kind="ops", full_name="Golden Operations", email="golden.narrations@example.test")
    db.add(ops)
    db.flush()
    statement = BankStatement(filename="golden-narrations.csv", mime_type="text/csv", sha256="1" * 64, size_bytes=1,
                              source="csv", uploaded_by=ops.id, notes=[])
    db.add(statement)
    db.flush()
    return statement.id


def read_lines(db, llm, narrations: list[str], amounts: list[str]):
    """One normalise call over the lines, as ingest makes; returns the readings and who read them."""
    lines = [RawLine(STATEMENT_DAY, text, Decimal(amount)) for text, amount in zip(narrations, amounts)]
    return normalise(db, llm, scratch_statement(db), lines)


@suite("narration_reader", tier="live")
def golden_narrations(ctx: EvalContext) -> SuiteResult:
    golden_cases = golden.load("narration_reader/narrations")["cases"]
    with scratch_db() as db:
        readings, read_by = read_lines(db, ctx.llm, [c["narration"] for c in golden_cases],
                                       [c["amount"] for c in golden_cases])
        cost = ai_cost(db)
    cases = []
    for c, reading in zip(golden_cases, readings):
        if read_by == "rules":  # normalise fell back: Gemini could not be reached, so nothing was learned about it
            cases.append(CaseResult(c["id"], "error", detail="The model could not be reached; rules read the line."))
            continue
        actual = {"remitter": reading.remitter, "reference": reading.reference}
        ok = _same(reading.remitter, c["expect"]["remitter"]) and _same(reading.reference, c["expect"]["reference"])
        cases.append(CaseResult(c["id"], "pass" if ok else "fail", expected=c["expect"], actual=actual,
                                detail=c["why"], cost_usd=round(cost / len(golden_cases), 6)))
    value = share_passing(cases)
    passed = sum(c.outcome == "pass" for c in cases)
    return rate("narration_reader", "golden", "live", cases,
                bar=f"Remitter and reference right in at least {NARRATION_BAR:.0%} of twelve golden narrations",
                metric=f"{passed} of {len(cases)} narrations read right", value=value, threshold=NARRATION_BAR)
