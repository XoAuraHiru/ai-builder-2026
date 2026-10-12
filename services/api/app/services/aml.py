"""Transaction monitoring (blueprint D7): a scenario library adapted to US practice, run over the ledger, the bank
statement lines and the order book, plus an anomaly score from the k-means model (app/ml/aml_model.py).

Each scenario is a fixed rule with its thresholds below, and every alert carries the exact rows behind it as evidence:
instructions, postings, statement lines, orders. An alert is raised once; its fingerprint is the scenario, the person
and the evidence ids. The MLRO decides every alert (app/services/compliance_ai.py).
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from itertools import permutations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import emit
from app.markets.quotes import NEW_YORK
from app.ml.aml_model import FEATURES, LABELS, AmlModel
from app.models import Account, AmlAlert, Instruction, Person, Posting, ReconMatch, StatementLine, TradeOrder
from app.models.base import utcnow
from app.services.devices import aware
from app.services.reconciliation import name_similarity

LOOKBACK_DAYS = 30
STRUCTURING_LOW, STRUCTURING_HIGH = Decimal("8500"), Decimal("10000")  # just under the $10,000 reporting threshold
STRUCTURING_COUNT, STRUCTURING_DAYS = 3, 7
RAPID_DAYS, RAPID_SHARE, RAPID_MINIMUM = 10, Decimal("0.75"), Decimal("10000")
ROUND_TRIP_DAYS, ROUND_TRIP_TOLERANCE = 14, Decimal("0.10")
VELOCITY_COUNT, VELOCITY_DAYS = 5, 7
DORMANT_DAYS, DORMANT_AMOUNT = 180, Decimal("25000")
HIGH_RISK_COUNTRIES = {"IR": "Iran", "KP": "North Korea", "MM": "Myanmar"}  # FATF call-for-action jurisdictions
LIVE = ("received", "accepted", "priced", "allocated", "settled")


@dataclass
class Finding:
    scenario: str
    title: str
    severity: str
    score: float
    person_id: str
    account_id: str | None
    summary: str
    evidence: list[dict] = field(default_factory=list)


def money(x) -> str:
    return f"${Decimal(x):,.2f}"


def day_words(d: date) -> str:
    return f"{d:%B} {d.day}"


def ny_date(moment: datetime) -> date:
    return aware(moment).astimezone(NEW_YORK).date()


def evidence(kind: str, row_id: str, day: date, amount, detail: str) -> dict:
    return {"kind": kind, "id": row_id, "date": day.isoformat(),
            "amount": None if amount is None else f"{Decimal(amount):.2f}", "detail": detail}


def _accounts(db: Session) -> dict[str, Account]:
    return {a.id: a for a in db.scalars(select(Account)).all()}


def _subscriptions(db: Session, since: date) -> list[Instruction]:
    rows = db.scalars(select(Instruction).where(Instruction.type == "subscribe", Instruction.state.in_(LIVE))).all()
    return [i for i in rows if ny_date(i.requested_at) >= since]


def structuring(db: Session, today: date) -> list[Finding]:
    accounts = _accounts(db)
    by_person: dict[str, list[Instruction]] = defaultdict(list)
    for i in _subscriptions(db, today - timedelta(days=LOOKBACK_DAYS)):
        if STRUCTURING_LOW <= i.amount < STRUCTURING_HIGH:
            by_person[accounts[i.account_id].person_id].append(i)
    out = []
    for person_id, rows in by_person.items():
        rows.sort(key=lambda i: aware(i.requested_at))
        best: list[Instruction] = []
        for k, first in enumerate(rows):
            window = [r for r in rows[k:]
                      if (ny_date(r.requested_at) - ny_date(first.requested_at)).days < STRUCTURING_DAYS]
            if len(window) > len(best):
                best = window
        if len(best) < STRUCTURING_COUNT:
            continue
        total = sum((r.amount for r in best), Decimal("0"))
        span = (ny_date(best[-1].requested_at) - ny_date(best[0].requested_at)).days + 1
        out.append(Finding(
            "structuring", "Possible structuring", "high", 0.9, person_id, best[0].account_id,
            f"{len(best)} subscriptions between {money(STRUCTURING_LOW)} and {money(STRUCTURING_HIGH)} within {span} "
            f"days, {money(total)} in all: each just under the {money(STRUCTURING_HIGH)} reporting threshold.",
            [evidence("instruction", r.id, ny_date(r.requested_at), r.amount,
                      f"Subscription of {money(r.amount)} on {day_words(ny_date(r.requested_at))}") for r in best]))
    return out


def rapid_in_out(db: Session, today: date) -> list[Finding]:
    since = today - timedelta(days=LOOKBACK_DAYS)
    accounts = _accounts(db)
    rows = db.scalars(select(Posting).where(
        Posting.instrument_type == "fund", Posting.posting_type.in_(("subscription", "redemption")),
        Posting.value_date >= since - timedelta(days=RAPID_DAYS))).all()
    by_account: dict[str, list[Posting]] = defaultdict(list)
    for p in rows:
        by_account[p.account_id].append(p)
    out = []
    for account_id, postings in by_account.items():
        best = None
        for gone in (p for p in postings if p.posting_type == "redemption" and p.value_date >= since):
            came = [p for p in postings if p.posting_type == "subscription"
                    and 0 <= (gone.value_date - p.value_date).days <= RAPID_DAYS]
            paid_in = sum((-p.cash for p in came), Decimal("0"))
            if paid_in >= RAPID_MINIMUM and gone.cash >= RAPID_SHARE * paid_in \
                    and (best is None or gone.cash > best[0].cash):
                best = (gone, came, paid_in)
        if best is None:
            continue
        gone, came, paid_in = best
        days = (gone.value_date - min(p.value_date for p in came)).days
        share = round(float(gone.cash / paid_in * 100))
        out.append(Finding(
            "rapid_in_out", "Money in and straight out", "high", 0.85, accounts[account_id].person_id, account_id,
            f"{money(paid_in)} paid in and {money(gone.cash)} taken out {days} days later, {share}% of what came in: "
            "the pattern of an account used to pass money through.",
            [evidence("posting", p.id, p.value_date, -p.cash, f"Subscription of {money(-p.cash)} into {p.instrument}")
             for p in sorted(came, key=lambda p: p.value_date)]
            + [evidence("posting", gone.id, gone.value_date, gone.cash,
                        f"Redemption of {money(gone.cash)} from {gone.instrument}")]))
    return out


def third_party_funding(db: Session, today: date) -> list[Finding]:
    since = today - timedelta(days=LOOKBACK_DAYS)
    accounts = _accounts(db)
    out = []
    for match in db.scalars(select(ReconMatch).where(ReconMatch.state == "accepted")).all():
        lines = db.scalars(select(StatementLine).where(StatementLine.id.in_(match.line_ids))).all()
        for i in db.scalars(select(Instruction).where(Instruction.id.in_(match.instruction_ids))).all():
            account = accounts[i.account_id]
            holder = account.person.full_name
            strangers = [x for x in lines if x.remitter and x.value_date >= since
                         and name_similarity(x.remitter, holder) < 0.5]
            if not strangers:
                continue
            out.append(Finding(
                "third_party_funding", "Paid by someone else", "medium", 0.6, account.person_id, account.id,
                f"A {money(i.amount)} subscription for {holder} was paid by {strangers[0].remitter}, not the account "
                "holder.",
                [evidence("instruction", i.id, ny_date(i.requested_at), i.amount,
                          f"Subscription of {money(i.amount)} by {holder}, account {account.number}")]
                + [evidence("statement_line", x.id, x.value_date, x.amount,
                            f"Bank credit from {x.remitter}: {x.description}") for x in strangers]))
    return out


def linked_round_trip(db: Session, today: date) -> list[Finding]:
    since = today - timedelta(days=LOOKBACK_DAYS)
    groups: dict[str, list[Account]] = defaultdict(list)
    for account in db.scalars(select(Account).where(Account.bank_index.is_not(None))).all():
        groups[account.bank_index].append(account)
    subscriptions = _subscriptions(db, since)
    out = []
    for group in groups.values():
        for a, b in permutations(group, 2):
            if a.person_id == b.person_id:
                continue
            outs = db.scalars(select(Posting).where(Posting.account_id == a.id, Posting.posting_type == "redemption",
                                                    Posting.value_date >= since)).all()
            ins = [i for i in subscriptions if i.account_id == b.id]
            pair = next(((o, i) for o in outs for i in ins
                         if 0 <= (ny_date(i.requested_at) - o.value_date).days <= ROUND_TRIP_DAYS
                         and abs(i.amount - o.cash) <= ROUND_TRIP_TOLERANCE * o.cash), None)
            if pair is None:
                continue
            o, i = pair
            gap = (ny_date(i.requested_at) - o.value_date).days
            out.append(Finding(
                "linked_round_trip", "Money moved between linked accounts", "high", 0.8, b.person_id, b.id,
                f"{money(o.cash)} left {a.person.full_name}'s account and {money(i.amount)} came into "
                f"{b.person.full_name}'s {gap} days later; both accounts are paid from the same bank account.",
                [evidence("posting", o.id, o.value_date, o.cash,
                          f"Redemption of {money(o.cash)} by {a.person.full_name}, account {a.number}"),
                 evidence("instruction", i.id, ny_date(i.requested_at), i.amount,
                          f"Subscription of {money(i.amount)} by {b.person.full_name}, account {b.number}"),
                 evidence("bank_link", f"bank:{a.bank_index[:12]}", today, None,
                          f"Accounts {a.number} and {b.number} share the bank account ending "
                          f"{a.bank_last4 or '????'}")]))
    return out


def velocity(db: Session, today: date) -> list[Finding]:
    since = today - timedelta(days=VELOCITY_DAYS)
    accounts = _accounts(db)
    events: dict[str, list[tuple]] = defaultdict(list)
    for i in db.scalars(select(Instruction)).all():
        if ny_date(i.requested_at) >= since:
            events[i.account_id].append((aware(i.requested_at), "instruction", i.id, i.amount or i.units,
                                         f"{i.type.title()} instruction"))
    for o in db.scalars(select(TradeOrder)).all():
        if ny_date(o.created_at) >= since:
            events[o.account_id].append((aware(o.created_at), "order", o.id, o.estimated_value,
                                         f"{o.side.title()} {o.quantity} {o.symbol}"))
    out = []
    for account_id, items in events.items():
        items.sort(key=lambda x: x[0])
        for k, first in enumerate(items):
            window = [x for x in items[k:] if x[0] - first[0] <= timedelta(hours=24)]
            if len(window) >= VELOCITY_COUNT:
                out.append(Finding(
                    "velocity", "A burst of activity", "medium", 0.5, accounts[account_id].person_id, account_id,
                    f"{len(window)} instructions and orders within 24 hours, against an ordinary pace of a few a month.",
                    [evidence(kind, row_id, ny_date(moment), amount, detail)
                     for moment, kind, row_id, amount, detail in window]))
                break
    return out


def dormant_reactivation(db: Session, today: date) -> list[Finding]:
    since = today - timedelta(days=LOOKBACK_DAYS)
    accounts = _accounts(db)
    instructions = db.scalars(select(Instruction)).all()
    orders = db.scalars(select(TradeOrder)).all()
    out = []
    for i in _subscriptions(db, since):
        if i.amount < DORMANT_AMOUNT:
            continue
        moment = aware(i.requested_at)
        before = [aware(x.requested_at) for x in instructions if x.account_id == i.account_id
                  and aware(x.requested_at) < moment]
        before += [aware(o.created_at) for o in orders if o.account_id == i.account_id and aware(o.created_at) < moment]
        if not before or (moment - max(before)).days < DORMANT_DAYS:
            continue
        quiet = (moment - max(before)).days
        out.append(Finding(
            "dormant_reactivation", "A quiet account wakes with a large payment", "medium", 0.6,
            accounts[i.account_id].person_id, i.account_id,
            f"{money(i.amount)} arrived after {quiet} days without any activity.",
            [evidence("instruction", i.id, ny_date(i.requested_at), i.amount,
                      f"Subscription of {money(i.amount)} after {quiet} quiet days")]))
    return out


def high_risk_jurisdiction(db: Session, today: date) -> list[Finding]:
    since = today - timedelta(days=LOOKBACK_DAYS)
    accounts = _accounts(db)
    recent: dict[str, list[Instruction]] = defaultdict(list)
    for i in db.scalars(select(Instruction)).all():
        if ny_date(i.requested_at) >= since:
            recent[accounts[i.account_id].person_id].append(i)
    out = []
    for person in db.scalars(select(Person).where(Person.country.in_(tuple(HIGH_RISK_COUNTRIES)))).all():
        rows = recent.get(person.id, [])
        if not rows:
            continue
        out.append(Finding(
            "high_risk_jurisdiction", "Activity linked to a high-risk jurisdiction", "high", 0.7, person.id,
            rows[0].account_id,
            f"{person.full_name} is recorded in {HIGH_RISK_COUNTRIES[person.country]}, a FATF call-for-action "
            f"jurisdiction, and placed {len(rows)} instruction{'s' if len(rows) != 1 else ''} in the last "
            f"{LOOKBACK_DAYS} days.",
            [evidence("instruction", i.id, ny_date(i.requested_at), i.amount or None,
                      f"{i.type.title()} instruction") for i in rows]))
    return out


def account_features(db: Session, account: Account, today: date) -> dict:
    since = today - timedelta(days=90)
    instructions = [i for i in db.scalars(select(Instruction).where(Instruction.account_id == account.id,
                                                                    Instruction.state.in_(LIVE))).all()
                    if ny_date(i.requested_at) >= since]
    subscriptions = [i for i in instructions if i.type == "subscribe"]
    redemptions = db.scalars(select(Posting).where(Posting.account_id == account.id,
                                                   Posting.posting_type == "redemption",
                                                   Posting.value_date >= since)).all()
    orders = [o for o in db.scalars(select(TradeOrder).where(TradeOrder.account_id == account.id)).all()
              if ny_date(o.created_at) >= since]
    funded = {i.id for i in subscriptions}
    payers = set()
    for match in db.scalars(select(ReconMatch).where(ReconMatch.state == "accepted")).all():
        if funded.intersection(match.instruction_ids):
            payers.update((x.remitter or "").lower() for x in db.scalars(
                select(StatementLine).where(StatementLine.id.in_(match.line_ids))).all() if x.remitter)
    movements = [i.amount for i in subscriptions] + [p.cash for p in redemptions]
    return {"inflow_usd": float(sum((i.amount for i in subscriptions), Decimal("0"))),
            "outflow_usd": float(sum((p.cash for p in redemptions), Decimal("0"))),
            "n_instructions": len(instructions),
            "n_orders": len(orders), "max_single_usd": float(max(movements, default=Decimal("0"))),
            "distinct_payers": max(1, len(payers))}


def _shown(feature: str, value: float) -> str:
    return f"${value:,.0f}" if feature.endswith("_usd") else f"{value:,.0f}"


def anomalies(db: Session, today: date, model: AmlModel) -> list[Finding]:
    out = []
    accounts = db.scalars(select(Account).join(Person, Account.person_id == Person.id)
                          .where(Person.kind == "investor")).all()
    for account in accounts:
        x = account_features(db, account, today)
        distance = model.distance(x)
        if distance <= model.threshold:
            continue
        z = dict(zip(FEATURES, model.standardise(x)))
        top = sorted(FEATURES, key=lambda f: -abs(z[f]))[:3]
        out.append(Finding(
            "anomaly", "Unusual account behaviour", "low", round(min(1.0, distance / (2 * model.threshold)), 2),
            account.person_id, account.id,
            f"The last 90 days of account {account.number} sit far from how ordinary accounts behave (distance "
            f"{distance:.1f} against a threshold of {model.threshold:.1f}), mostly because of: "
            + ", ".join(LABELS[f].lower() for f in top) + ".",
            [evidence("feature", f"{account.number}:{f}:{today:%Y-%m}", today, x[f] if f.endswith("_usd") else None,
                      f"{LABELS[f]}: {_shown(f, x[f])}, where ordinary accounts sit near {_shown(f, model.means[f])}")
             for f in top]))
    return out


SCENARIOS = (structuring, rapid_in_out, third_party_funding, linked_round_trip, velocity, dormant_reactivation,
             high_risk_jurisdiction)


def fingerprint(finding: Finding) -> str:
    ids = ",".join(sorted(e["id"] for e in finding.evidence))
    return hashlib.sha256(f"{finding.scenario}|{finding.person_id}|{ids}".encode()).hexdigest()


def run_monitoring(db: Session, today: date | None = None, model: AmlModel | None = None) -> list[AmlAlert]:
    db.flush()  # sessions do not autoflush: rows the caller added must be visible to the scenarios
    today = today or ny_date(utcnow())
    model = model or AmlModel.load()
    findings = [f for scenario in SCENARIOS for f in scenario(db, today)] + anomalies(db, today, model)
    raised: list[AmlAlert] = []
    for f in findings:
        mark = fingerprint(f)
        if db.scalar(select(AmlAlert.id).where(AmlAlert.fingerprint == mark)) is not None:
            continue
        alert = AmlAlert(scenario=f.scenario, title=f.title, severity=f.severity, score=f.score,
                         person_id=f.person_id, account_id=f.account_id, summary=f.summary, evidence=f.evidence,
                         fingerprint=mark, state="open")
        db.add(alert)
        db.flush()
        raised.append(alert)
        emit("AlertRaised", {"alert_id": alert.id, "scenario": f.scenario, "severity": f.severity,
                             "person_id": f.person_id})
    return raised
