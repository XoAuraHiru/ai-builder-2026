"""The reconciliation agent (blueprint D5): an ADK agent that works the fuzzy and combination tiers.

Rules have already proposed exact references and unique amounts. The agent reads what is left with scoring tools and
proposes a match only when the evidence supports it, with a confidence and a sentence of reasoning; the tools check every
id and amount, so it cannot use a line twice, claim a subscription that is not open, or pass off a combination that does
not add up. Without Gemini, or if the agent fails, the scorer proposes the strongest candidates on its own and the
proposals say so. A person accepts or rejects every proposal either way.
"""
from __future__ import annotations

import time
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.agents.runtime import DATA_RULE, AgentUnavailable, fast_config, model_name, run_agent, usage_tracker
from app.ai.decisions import record_decision
from app.ai.llm import LLMResult, price_usd
from app.config import get_settings
from app.services.reconciliation import (busy_instruction_ids, candidates, fallback_proposals, name_similarity,
                                         open_receipts, propose, propose_by_rules, score, unmatched_deposits)

RECONCILER = f"""You reconcile Atrium's client money bank account. {DATA_RULE}
Rules have already matched exact references and unique amounts. Work through every remaining deposit line:
- call list_unmatched_lines and list_open_receipts first;
- for each line call score_candidates(line_id). A reference one or two characters away, the same or a very close amount,
  and the account holder's name are the evidence for a fuzzy match;
- when two or three lines from the same payer might together pay one subscription, call
  check_combination(line_ids, instruction_id);
- propose with propose_match(line_ids, instruction_id, confidence, reasoning) only when the evidence supports it.
  Confidence is between 0 and 1; reasoning is one sentence naming the evidence;
- leave a line alone when nothing fits: a person will look at it. Never use a line or a subscription twice.
Finish with one sentence saying what you proposed and what you left."""


def build_reconciler(lines, receipts, model, proposals: list, trace: list, usage: dict | None = None):
    from google.adk.agents import Agent

    by_line = {line.id: line for line in lines}
    by_receipt = {r.instruction_id: r for r in receipts}
    used_lines: set[str] = set()
    used_receipts: set[str] = set()

    def note(tool: str, label: str) -> None:
        trace.append({"tool": tool, "label": label})

    def list_unmatched_lines() -> dict:
        """Return the deposit lines that are not matched or proposed yet."""
        note("list_unmatched_lines", f"Read {len(by_line)} unmatched deposit lines")
        return {"lines": [{"line_id": x.id, "date": x.value_date.isoformat(), "amount": str(x.amount),
                           "description": x.description, "payer": x.remitter, "reference": x.reference}
                          for x in lines if x.id not in used_lines]}

    def list_open_receipts() -> dict:
        """Return the subscriptions still waiting for their money."""
        note("list_open_receipts", f"Read {len(by_receipt)} subscriptions waiting for money")
        return {"receipts": [{"instruction_id": r.instruction_id, "reference": r.reference, "holder": r.holder,
                              "amount": str(r.amount), "fund": r.fund_name, "requested_on": r.requested_on.isoformat()}
                             for r in receipts if r.instruction_id not in used_receipts]}

    def score_candidates(line_id: str) -> dict:
        """Score the open subscriptions against one line: reference distance, amount and payer name, with reasons."""
        line = by_line.get(line_id)
        if line is None:
            return {"error": "Unknown line."}
        note("score_candidates", f"Scored the candidates for “{line.description[:48]}”")
        found = candidates(line, [r for r in receipts if r.instruction_id not in used_receipts])
        return {"candidates": [{"instruction_id": c.instruction_id, "score": c.score, "reasons": list(c.reasons)}
                               for c in found]}

    def check_combination(line_ids: list[str], instruction_id: str) -> dict:
        """Check whether these lines together pay one subscription: their total, the amount due, and one payer."""
        chosen = [by_line[i] for i in line_ids if i in by_line]
        receipt = by_receipt.get(instruction_id)
        if len(chosen) != len(line_ids) or len(chosen) < 2 or receipt is None:
            return {"error": "Name two or three known lines and an open subscription."}
        total = sum((x.amount for x in chosen), Decimal("0"))
        same = all(name_similarity(x.remitter, chosen[0].remitter) >= 0.5 for x in chosen[1:])
        note("check_combination", f"Checked {len(chosen)} lines against {receipt.reference}")
        return {"total": str(total), "due": str(receipt.amount), "same_payer": same,
                "fits": total == receipt.amount and same}

    def propose_match(line_ids: list[str], instruction_id: str, confidence: float, reasoning: str) -> dict:
        """Propose that these lines pay this subscription. A person reviews every proposal."""
        chosen = [by_line.get(i) for i in line_ids]
        receipt = by_receipt.get(instruction_id)
        note("propose_match", f"Proposed {len(line_ids)} line(s) for "
                              f"{receipt.reference if receipt else 'an unknown subscription'}")
        if not chosen or None in chosen or receipt is None:
            return {"error": "Unknown line or subscription."}
        if used_lines.intersection(line_ids) or instruction_id in used_receipts:
            return {"error": "A line or the subscription is already in a proposal."}
        total = sum((x.amount for x in chosen), Decimal("0"))
        if len(chosen) > 1 and total != receipt.amount:
            return {"error": "These lines do not add up to the amount due."}
        reasons = [" ".join(str(reasoning).split())[:300]]
        reasons += (list(score(chosen[0], receipt).reasons) if len(chosen) == 1
                    else [f"{len(chosen)} payments total ${total:,.2f}, the amount due."])
        proposals.append({"line_ids": list(line_ids), "instruction_id": instruction_id,
                          "tier": "combination" if len(chosen) > 1 else "fuzzy",
                          "confidence": max(0.0, min(1.0, float(confidence))), "evidence": reasons})
        used_lines.update(line_ids)
        used_receipts.add(instruction_id)
        return {"ok": True}

    return Agent(name="reconciler", model=model, instruction=RECONCILER, generate_content_config=fast_config(),
                 after_model_callback=usage_tracker(usage),
                 tools=[list_unmatched_lines, list_open_receipts, score_candidates, check_combination, propose_match])


def reconcile(db: Session, model, now: datetime) -> dict:
    rules = propose_by_rules(db)
    lines = unmatched_deposits(db)
    busy = busy_instruction_ids(db)
    receipts = [r for r in open_receipts(db) if r.instruction_id not in busy]
    proposals: list[dict] = []
    trace: list[dict] = []
    used_agent, summary = False, "Nothing was left for the agent."
    if lines and receipts:
        if model_name(model) == "offline-agent":
            proposals = fallback_proposals(lines, receipts)
            summary = "Gemini is not connected here, so the scorer proposed the strongest remaining matches."
        else:
            usage = {"in": 0, "out": 0}
            agent = build_reconciler(lines, receipts, model, proposals, trace, usage)
            started = time.perf_counter()
            try:
                summary = run_agent(agent, "Reconcile the remaining deposit lines.").strip()
                used_agent = True
            except AgentUnavailable:
                proposals = fallback_proposals(lines, receipts)
                summary = "The agent was unavailable, so the scorer proposed the strongest remaining matches."
            else:
                name = model_name(model)
                result = LLMResult(parsed={"summary": summary, "proposals": proposals,
                                           "tools": [t["tool"] for t in trace]},
                                   model=name, tokens_in=usage["in"], tokens_out=usage["out"],
                                   latency_ms=int((time.perf_counter() - started) * 1000),
                                   cost_usd=price_usd(get_settings(), name, usage["in"], usage["out"]))
                record_decision(db, agent="reconciler", purpose="reconciliation", result=result,
                                subject_type="bank_statement", subject_id=lines[0].statement_id,
                                input_text=RECONCILER)
    by_line = {line.id: line for line in lines}
    by_receipt = {r.instruction_id: r for r in receipts}
    by = "agent" if used_agent else "scorer"
    made = [propose(db, [by_line[i] for i in p["line_ids"]], by_receipt[p["instruction_id"]], p["tier"],
                    p["confidence"], p["evidence"], by) for p in proposals]
    db.flush()
    return {"rules": len(rules), "agent": len(made) if used_agent else 0, "scorer": 0 if used_agent else len(made),
            "summary": summary, "trace": trace, "used_agent": used_agent}
