"""Reconciliation (blueprint D5): matching deposits on the client money bank statement with the subscriptions Atrium is
waiting for money for.

Rules take the clear cases: the payment reference and the amount both match, or a line without a reference, paid by
the account holder, carries an amount that exactly one open subscription and exactly one line share. Everything else is
for the reconciliation agent (app/agents/reconciler.py), which uses the scorer below; without Gemini the scorer proposes
on its own. A person accepts or rejects every proposal, and a match built by hand needs a second person's approval with
a one-time code (D6). An accepted match funds the subscription: settled at once if it is already allocated, otherwise
when it is.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from itertools import combinations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import emit
from app.models import (Account, Approval, Fund, Instruction, InstructionStep, Person, ReconMatch, StatementLine)
from app.services.allocation import funded_ids, settle
from app.services.approvals import OpsError, request_approval
from app.services.devices import aware
from app.services.instructions import payment_reference

OPEN_STATES = ("accepted", "priced", "allocated")
EXACT_CONFIDENCE, UNIQUE_CONFIDENCE, COMBINATION_CONFIDENCE = 0.99, 0.85, 0.8
FUZZY_MIN = 0.7
AMOUNT_TOLERANCE = Decimal("1.00")
TIER_WORDS = {"exact_reference": "the reference and amount match", "unique_amount": "a unique amount",
              "fuzzy": "a close match", "combination": "several payments together", "manual": "a manual match"}


class ReconError(OpsError):
    pass


@dataclass(frozen=True)
class Receipt:
    instruction_id: str
    reference: str
    account_number: str
    holder: str
    amount: Decimal
    fund_name: str
    requested_on: date


@dataclass(frozen=True)
class Candidate:
    instruction_id: str
    score: float
    reasons: tuple[str, ...]


def code_of(reference: str | None) -> str | None:
    """The characters after ATR, upper case, without the hyphen."""
    if not reference:
        return None
    text = re.sub(r"[^0-9A-Z]", "", reference.upper())
    return text[3:] if text.startswith("ATR") and len(text) > 3 else None


def edit_distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def _words(text: str | None) -> set[str]:
    return {w for w in re.split(r"[^a-z]+", (text or "").lower()) if len(w) > 1}


def name_similarity(a: str | None, b: str | None) -> float:
    x, y = _words(a), _words(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def open_receipts(db: Session) -> list[Receipt]:
    """Subscriptions still waiting for their money: not rejected or reversed, and in no accepted match."""
    funded = funded_ids(db)
    names = {f.code: f.name for f in db.scalars(select(Fund)).all()}
    rows = db.execute(select(Instruction, Account).join(Account, Instruction.account_id == Account.id)
                      .where(Instruction.type == "subscribe", Instruction.state.in_(OPEN_STATES))
                      .order_by(Instruction.requested_at)).all()
    return [Receipt(i.id, payment_reference(i.id), a.number, a.person.full_name, i.amount,
                    names.get(i.fund_code, i.fund_code), aware(i.requested_at).date())
            for i, a in rows if i.id not in funded]


def unmatched_deposits(db: Session) -> list[StatementLine]:
    return db.scalars(select(StatementLine).where(StatementLine.state == "unmatched", StatementLine.amount > 0)
                      .order_by(StatementLine.value_date, StatementLine.line_no)).all()


def busy_instruction_ids(db: Session) -> set[str]:
    """Subscriptions already in a proposal or a manual match waiting for approval."""
    rows = db.scalars(select(ReconMatch.instruction_ids).where(
        ReconMatch.state.in_(("proposed", "awaiting_approval")))).all()
    return {i for ids in rows for i in ids}


def score(line: StatementLine, receipt: Receipt) -> Candidate:
    total, reasons = 0.0, []
    code, expected = code_of(line.reference), code_of(receipt.reference)
    if code:
        distance = edit_distance(code, expected)
        if distance == 0:
            total += 0.6
            reasons.append(f"The reference {line.reference} matches.")
        elif distance <= 2:
            total += 0.6 - 0.15 * distance
            reasons.append(f"The reference {line.reference} is {distance} character{'s' if distance > 1 else ''} away "
                           f"from {receipt.reference}.")
        else:
            reasons.append(f"The reference {line.reference} does not match {receipt.reference}.")
    if line.amount == receipt.amount:
        total += 0.3
        reasons.append(f"The amount ${line.amount:,.2f} matches.")
    elif abs(line.amount - receipt.amount) <= AMOUNT_TOLERANCE:
        total += 0.15
        reasons.append(f"The amount differs by ${abs(line.amount - receipt.amount):,.2f}.")
    similarity = name_similarity(line.remitter, receipt.holder)
    total += 0.1 * similarity
    if similarity >= 0.5:
        reasons.append(f"The payer {line.remitter} matches the account holder.")
    elif line.remitter:
        reasons.append(f"The payer {line.remitter} is not the account holder, {receipt.holder}.")
    return Candidate(receipt.instruction_id, round(total, 2), tuple(reasons))


def candidates(line: StatementLine, receipts: list[Receipt], top: int = 3) -> list[Candidate]:
    found = [score(line, r) for r in receipts]
    return sorted((c for c in found if c.score > 0), key=lambda c: -c.score)[:top]


def propose(db: Session, lines: list[StatementLine], receipt: Receipt, tier: str, confidence: float,
            reasons: list[str] | tuple[str, ...], by: str) -> ReconMatch:
    match = ReconMatch(line_ids=[line.id for line in lines], instruction_ids=[receipt.instruction_id], tier=tier,
                       confidence=round(float(confidence), 2), evidence=list(reasons), proposed_by=by)
    db.add(match)
    for line in lines:
        line.state = "proposed"
    db.flush()
    emit("MatchProposed", {"match_id": match.id, "tier": tier, "confidence": match.confidence, "proposed_by": by,
                           "instruction_ids": match.instruction_ids})
    return match


def propose_by_rules(db: Session) -> list[ReconMatch]:
    lines = unmatched_deposits(db)
    busy = busy_instruction_ids(db)
    receipts = [r for r in open_receipts(db) if r.instruction_id not in busy]
    by_code = {code_of(r.reference): r for r in receipts}
    made: list[ReconMatch] = []
    used: set[str] = set()
    for line in lines:
        receipt = by_code.get(code_of(line.reference)) if line.reference else None
        if receipt and receipt.instruction_id not in used and line.amount == receipt.amount:
            made.append(propose(db, [line], receipt, "exact_reference", EXACT_CONFIDENCE,
                                score(line, receipt).reasons, "rules"))
            used.add(receipt.instruction_id)
    remaining = [line for line in lines if line.state == "unmatched"]
    for line in remaining:
        if line.reference or line.state != "unmatched":
            continue  # a quoted reference that is not exact is the agent's to judge
        same_receipts = [r for r in receipts if r.instruction_id not in used and r.amount == line.amount]
        same_lines = [x for x in remaining if x.amount == line.amount and not x.reference]
        if len(same_receipts) == 1 and len(same_lines) == 1 \
                and name_similarity(line.remitter, same_receipts[0].holder) >= 0.5:
            receipt = same_receipts[0]
            made.append(propose(db, [line], receipt, "unique_amount", UNIQUE_CONFIDENCE,
                                ("Only one open subscription and one statement line carry this amount.",
                                 *score(line, receipt).reasons), "rules"))
            used.add(receipt.instruction_id)
    return made


def combination_candidates(lines: list[StatementLine], receipts: list[Receipt]):
    """Two or three lines from one payer that together equal one open subscription."""
    out = []
    for size in (2, 3):
        for group in combinations(lines, size):
            payer = group[0].remitter
            if not payer or any(name_similarity(x.remitter, payer) < 0.5 for x in group[1:]):
                continue
            total = sum((x.amount for x in group), Decimal("0"))
            for receipt in receipts:
                if receipt.amount == total:
                    out.append((list(group), receipt,
                                (f"{size} payments from {payer} total ${total:,.2f}, the amount due.",)))
    return out


def fallback_proposals(lines: list[StatementLine], receipts: list[Receipt]) -> list[dict]:
    """What the scorer proposes on its own when the agent is not available: combinations first, then the strongest
    fuzzy candidate for each line, if it scores at least FUZZY_MIN."""
    out, used_lines, used_receipts = [], set(), set()
    for group, receipt, reasons in combination_candidates(lines, receipts):
        ids = [x.id for x in group]
        if used_lines.intersection(ids) or receipt.instruction_id in used_receipts:
            continue
        out.append({"line_ids": ids, "instruction_id": receipt.instruction_id, "tier": "combination",
                    "confidence": COMBINATION_CONFIDENCE, "evidence": list(reasons)})
        used_lines.update(ids)
        used_receipts.add(receipt.instruction_id)
    for line in lines:
        if line.id in used_lines:
            continue
        found = candidates(line, [r for r in receipts if r.instruction_id not in used_receipts], top=1)
        if found and found[0].score >= FUZZY_MIN:
            best = found[0]
            out.append({"line_ids": [line.id], "instruction_id": best.instruction_id, "tier": "fuzzy",
                        "confidence": best.score, "evidence": list(best.reasons)})
            used_lines.add(line.id)
            used_receipts.add(best.instruction_id)
    return out


def _confirm(db: Session, match: ReconMatch, person: Person, now: datetime) -> list[str]:
    match.state, match.decided_by, match.decided_at = "accepted", person.id, now
    for line in db.scalars(select(StatementLine).where(StatementLine.id.in_(match.line_ids))).all():
        line.state = "matched"
    settled = []
    for instruction in db.scalars(select(Instruction).where(Instruction.id.in_(match.instruction_ids))).all():
        if instruction.state == "allocated":
            settle(db, instruction, now, f"Settled: the payment was matched on the bank statement "
                                         f"({TIER_WORDS[match.tier]}).")
            settled.append(instruction.id)
        else:
            db.add(InstructionStep(instruction_id=instruction.id, state="funded",
                                   note="Payment received and matched on the bank statement; units are allocated "
                                        "at the next published price."))
    db.flush()
    emit("MatchAccepted", {"match_id": match.id, "tier": match.tier, "decided_by": person.id,
                           "instruction_ids": match.instruction_ids, "settled": settled})
    return settled


def accept(db: Session, match: ReconMatch, person: Person, now: datetime) -> ReconMatch:
    if match.tier == "manual":
        raise ReconError("A manual match is approved by a second person.")
    if match.state != "proposed":
        raise ReconError("This proposal has already been decided.")
    _confirm(db, match, person, now)
    return match


def reject(db: Session, match: ReconMatch, person: Person, now: datetime, note: str = "") -> ReconMatch:
    if match.state != "proposed":
        raise ReconError("This proposal has already been decided.")
    match.state, match.decided_by, match.decided_at, match.note = "rejected", person.id, now, note.strip() or None
    for line in db.scalars(select(StatementLine).where(StatementLine.id.in_(match.line_ids))).all():
        line.state = "unmatched"
    db.flush()
    emit("MatchRejected", {"match_id": match.id, "decided_by": person.id})
    return match


def request_manual_match(db: Session, line_ids: list[str], instruction_ids: list[str], requester: Person,
                         reason: str) -> Approval:
    lines = [db.get(StatementLine, i) for i in line_ids]
    if not lines or any(x is None or x.state != "unmatched" or x.amount <= 0 for x in lines):
        raise ReconError("Choose deposit lines that are not matched or proposed yet.")
    receipts = {r.instruction_id: r for r in open_receipts(db)}
    busy = busy_instruction_ids(db)
    if not instruction_ids or any(i not in receipts or i in busy for i in instruction_ids):
        raise ReconError("Choose subscriptions that are still waiting for their money.")
    paid = sum((x.amount for x in lines), Decimal("0"))
    due = sum((receipts[i].amount for i in instruction_ids), Decimal("0"))
    agreement = "They agree." if paid == due else f"They differ by ${abs(paid - due):,.2f}."
    evidence = [f"The lines total ${paid:,.2f} and the subscriptions total ${due:,.2f}. {agreement}",
                *[f"Line: {x.value_date:%B} {x.value_date.day}, ${x.amount:,.2f}, {x.description}" for x in lines],
                *[f"Subscription {receipts[i].reference}: {receipts[i].holder}, ${receipts[i].amount:,.2f} into "
                  f"{receipts[i].fund_name}" for i in instruction_ids]]
    match = ReconMatch(line_ids=list(line_ids), instruction_ids=list(instruction_ids), tier="manual",
                       confidence=1.0 if paid == due else 0.5, evidence=evidence, proposed_by=requester.email,
                       state="awaiting_approval")
    db.add(match)
    for line in lines:
        line.state = "proposed"
    db.flush()
    approval = request_approval(
        db, action="manual_match",
        payload={"match_id": match.id, "line_ids": list(line_ids), "instruction_ids": list(instruction_ids)},
        summary=(f"Match {len(lines)} statement line{'s' if len(lines) != 1 else ''} (${paid:,.2f}) with "
                 + ", ".join(f"{receipts[i].reference} for {receipts[i].holder}" for i in instruction_ids)),
        reason=reason, evidence=[{"label": "Evidence", "detail": e} for e in evidence], requested_by=requester)
    match.approval_id = approval.id
    db.flush()
    return approval


def execute_manual_match(db: Session, approval: Approval, approver: Person, now: datetime) -> dict:
    match = db.get(ReconMatch, approval.payload["match_id"])
    if match is None or match.state != "awaiting_approval":
        raise ReconError("This match is no longer waiting for approval.")
    return {"match_id": match.id, "settled": _confirm(db, match, approver, now)}


def reject_manual_match(db: Session, approval: Approval, now: datetime) -> None:
    match = db.get(ReconMatch, approval.payload["match_id"])
    if match is None or match.state != "awaiting_approval":
        return
    match.state, match.decided_at = "rejected", now
    for line in db.scalars(select(StatementLine).where(StatementLine.id.in_(match.line_ids))).all():
        line.state = "unmatched"
    db.flush()
