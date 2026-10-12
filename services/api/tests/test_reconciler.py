from datetime import date, datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator

import pytest
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from sqlalchemy import select

from app.agents.reconciler import reconcile
from app.agents.runtime import get_agent_model
from app.models import AIDecision, BankStatement, Instruction, ReconMatch, StatementLine
from app.seed.funds import seed_funds
from app.services.instructions import payment_reference
from app.services.reconciliation import code_of

NOW = datetime(2026, 10, 12, 15, tzinfo=timezone.utc)


class ScriptedLlm(BaseLlm):
    model: str = "scripted"
    responses: list[LlmResponse] = []

    async def generate_content_async(self, llm_request: LlmRequest,
                                     stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        yield self.responses.pop(0)


class FailingLlm(BaseLlm):
    model: str = "failing"

    async def generate_content_async(self, llm_request: LlmRequest,
                                     stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        raise RuntimeError("429 RESOURCE_EXHAUSTED")
        yield  # pragma: no cover


def call(name, **args):
    return LlmResponse(content=types.Content(role="model", parts=[
        types.Part(function_call=types.FunctionCall(name=name, args=args))]))


def say(text):
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


@pytest.fixture()
def remaining(db, account, staff):
    """Three subscriptions the rules cannot match: a mistyped reference, a split payment, and one with nothing to go on."""
    seed_funds(db)
    subs = []
    for amount in ("3000", "5000", "777"):
        row = Instruction(account_id=account.id, fund_code="ATR-BAL", type="subscribe", amount=Decimal(amount),
                          state="accepted", requested_at=NOW)
        db.add(row)
        db.flush()
        subs.append(row)
    statement = BankStatement(filename="s.csv", mime_type="text/csv", sha256="c" * 64, size_bytes=1, source="csv",
                              uploaded_by=staff["mei"].id, notes=[])
    db.add(statement)
    db.flush()
    code = code_of(payment_reference(subs[0].id))
    wrong = f"ATR-{code[:5]}{'0' if code[5] != '0' else '1'}{code[6:]}"
    lines = []
    for n, (amount, text, payer, ref) in enumerate([
            ("3000.00", f"ACH CREDIT PRIYA RAMAN REF {wrong}", "Priya Raman", wrong),
            ("3100.00", "ACH CREDIT PRIYA RAMAN PART 1 OF 2", "Priya Raman", None),
            ("1900.00", "ACH CREDIT PRIYA RAMAN PART 2 OF 2", "Priya Raman", None),
            ("2750.00", "WIRE IN KESTREL TRADING LTD REF INV 2231", "Kestrel Trading Ltd", None)], start=1):
        line = StatementLine(statement_id=statement.id, line_no=n, value_date=date(2026, 10, 12),
                             amount=Decimal(amount), description=text, remitter=payer, reference=ref)
        db.add(line)
        lines.append(line)
    db.commit()
    return subs, lines


def test_the_agent_proposes_with_reasons_and_is_logged(db, remaining):
    subs, lines = remaining
    model = ScriptedLlm(responses=[
        call("list_unmatched_lines"), call("list_open_receipts"),
        call("score_candidates", line_id=lines[0].id),
        call("propose_match", line_ids=[lines[0].id], instruction_id=subs[0].id, confidence=0.9,
             reasoning="One character of the reference differs; amount and payer match."),
        call("propose_match", line_ids=[lines[0].id], instruction_id=subs[2].id, confidence=0.5, reasoning="Again."),
        call("check_combination", line_ids=[lines[1].id, lines[2].id], instruction_id=subs[1].id),
        call("propose_match", line_ids=[lines[1].id, lines[2].id], instruction_id=subs[1].id, confidence=0.85,
             reasoning="Two payments from the holder add up to the amount due."),
        say("Proposed two matches; left the Kestrel wire for a person.")])
    out = reconcile(db, model, NOW)
    assert out["used_agent"] and out["agent"] == 2 and out["rules"] == 0
    matches = {m.tier: m for m in db.scalars(select(ReconMatch)).all()}
    assert {tier: (m.instruction_ids, m.proposed_by) for tier, m in matches.items()} == {
        "fuzzy": ([subs[0].id], "agent"), "combination": ([subs[1].id], "agent")}
    fuzzy = matches["fuzzy"]
    assert fuzzy.evidence[0].startswith("One character") and "1 character away" in fuzzy.evidence[1]
    assert [line.state for line in lines] == ["proposed", "proposed", "proposed", "unmatched"]
    assert [t["tool"] for t in out["trace"]].count("propose_match") == 3   # the refused duplicate is traced too
    assert db.scalars(select(AIDecision.purpose)).all() == ["reconciliation"]


def test_without_gemini_the_scorer_proposes_and_says_so(db, remaining):
    subs, lines = remaining
    out = reconcile(db, get_agent_model(), NOW)   # the offline model in tests
    assert not out["used_agent"] and out["scorer"] == 2 and "Gemini" in out["summary"]
    tiers = {m.tier: m.proposed_by for m in db.scalars(select(ReconMatch)).all()}
    assert tiers == {"combination": "scorer", "fuzzy": "scorer"}


def test_a_failing_agent_falls_back_to_the_scorer(db, remaining):
    out = reconcile(db, FailingLlm(), NOW)
    assert not out["used_agent"] and out["scorer"] == 2 and "unavailable" in out["summary"]
