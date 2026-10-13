"""Monitoring from production: how often people agree with each model's suggestion, and whether the inputs have
drifted from what the models were trained on, over the last 30 days, with the sample sizes shown.

A rate needs at least MIN_DECISIONS decisions; below that it is "not enough decisions yet", never 0% and never a trip.
"""
import math
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.governance.inventory import MODELS
from app.models import AmlAlert, Account, Lead, Person, ReconMatch, TradeOrder
from app.models.base import utcnow

WINDOW_DAYS = 30
MIN_DECISIONS = 10
AGREEMENT_FLOOR = 0.6
MIN_RECENT_LEADS = 20
PSI_WARN = 0.25
PSI_BINS = 10
PSI_FLOOR = 0.0001
PROPOSERS = ("agent", "scorer", "rules")
ANOMALY_TRAINING_SHARE = 0.01  # the threshold is the 99th percentile of ordinary accounts' distance (ml/aml_model.py)


def _aware(moment: datetime) -> datetime:
    from datetime import timezone

    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _window(now: datetime | None) -> tuple[datetime, datetime]:
    now = now or utcnow()
    return now - timedelta(days=WINDOW_DAYS), now


def _in(moment: datetime | None, since: datetime, now: datetime) -> bool:
    return moment is not None and since <= _aware(moment) <= now


def _rate(agreed: int, decided: int, **extra) -> dict:
    if decided < MIN_DECISIONS:
        return {"agreed": agreed, "decided": decided, "rate": None,
                "note": f"Not enough decisions yet ({decided} of {MIN_DECISIONS})", **extra}
    return {"agreed": agreed, "decided": decided, "rate": agreed / decided,
            "note": f"{round(100 * agreed / decided)}% of {decided} decisions in the last {WINDOW_DAYS} days", **extra}


def _reconciliation(db: Session, since: datetime, now: datetime) -> dict:
    rows = db.scalars(select(ReconMatch).where(ReconMatch.state.in_(("accepted", "rejected")),
                                               ReconMatch.proposed_by.in_(PROPOSERS))).all()
    by = {}
    for who in PROPOSERS:
        mine = [m for m in rows if m.proposed_by == who and _in(m.decided_at, since, now)]
        by[who] = _rate(sum(m.state == "accepted" for m in mine), len(mine))
    return {**by["agent"], "by": by}


def _case_reviews(db: Session, since: datetime, now: datetime) -> dict:
    agreed = decided = 0
    for alert in db.scalars(select(AmlAlert).where(AmlAlert.state.in_(("escalated", "closed")))).all():
        triage = (alert.ai_review or {}).get("triage")
        if not triage or triage == "request_information" or not _in(alert.decided_at, since, now):
            continue
        decided += 1
        agreed += (alert.state == "escalated") == (triage == "escalate")
    return _rate(agreed, decided)


def _held_orders(db: Session, since: datetime, now: datetime) -> dict:
    agreed = decided = 0
    for order in db.scalars(select(TradeOrder).where(TradeOrder.reviewed_at.is_not(None))).all():
        suggestion = (order.ai_review or {}).get("suggestion")
        if suggestion not in ("release", "reject") or not _in(order.reviewed_at, since, now):
            continue
        states = [step.get("state") for step in order.timeline or []]
        decision = "release" if "released" in states else "reject" if order.state == "rejected" else None
        if decision is None:
            continue
        decided += 1
        agreed += decision == suggestion
    return _rate(agreed, decided)


def agreement(db: Session, now: datetime | None = None) -> dict[str, dict]:
    """Per model, how often people's decisions matched its suggestion over the window."""
    since, now = _window(now)
    return {"reconciler_agent": _reconciliation(db, since, now), "case_reviewer": _case_reviews(db, since, now),
            "held_order_reviewer": _held_orders(db, since, now)}


_training_scores: list[int] | None = None


def training_scores() -> list[int]:
    """The Lead Score of every lead in the training history, through the committed model."""
    global _training_scores
    if _training_scores is None:
        from app.ml.lead_history import generate_lead_history
        from app.ml.lead_model import LeadModel

        model = LeadModel.load()
        _training_scores = [model.score({k: v for k, v in r.items() if k != "converted"})
                            for r in generate_lead_history(seed=7)]
    return _training_scores


def _shares(scores: list[int]) -> list[float]:
    counts = [0] * PSI_BINS
    for s in scores:
        counts[min(PSI_BINS - 1, max(0, int(s) * PSI_BINS // 100))] += 1
    return [max(PSI_FLOOR, c / len(scores)) for c in counts]


def psi(recent: list[int], expected: list[int]) -> float:
    """Population stability index over ten equal-width bins on 0 to 100."""
    a, e = _shares(recent), _shares(expected)
    return sum((x - y) * math.log(x / y) for x, y in zip(a, e))


def drift(db: Session, now: datetime | None = None) -> dict:
    since, now = _window(now)
    scores = [lead.lead_score for lead in db.scalars(select(Lead).where(Lead.lead_score.is_not(None))).all()
              if _in(lead.scored_at, since, now)]
    if len(scores) < MIN_RECENT_LEADS:
        lead_score = {"psi": None, "recent": len(scores), "warn": False,
                      "note": f"Not enough recently scored leads yet ({len(scores)} of {MIN_RECENT_LEADS})"}
    else:
        value = psi(scores, training_scores())
        lead_score = {"psi": round(value, 4), "recent": len(scores), "warn": value > PSI_WARN,
                      "note": ("shifted from training" if value > PSI_WARN else "stable") + f" (PSI {value:.2f})"}
    accounts = db.scalars(select(Account).join(Person, Account.person_id == Person.id)
                          .where(Person.kind == "investor")).all()
    flagged = {a.account_id for a in db.scalars(select(AmlAlert).where(AmlAlert.scenario == "anomaly")).all()
               if _in(a.created_at, since, now)}
    share = len(flagged) / len(accounts) if accounts else None
    anomaly = {"share": share, "flagged": len(flagged), "accounts": len(accounts),
               "training_share": ANOMALY_TRAINING_SHARE,
               "note": ("No investor accounts yet" if share is None else
                        f"{len(flagged)} of {len(accounts)} accounts flagged in the last {WINDOW_DAYS} days, against "
                        f"about {ANOMALY_TRAINING_SHARE:.0%} of ordinary accounts in training (the model's threshold)")}
    return {"lead_score": lead_score, "aml_anomaly": anomaly}


def monitoring(db: Session, now: datetime | None = None) -> dict:
    return {"agreement": agreement(db, now), "drift": drift(db, now), "window_days": WINDOW_DAYS}


def apply_monitoring_breakers(db: Session, now: datetime | None = None) -> list[str]:
    """Trip a High-tier model with a fallback when people agreed with it in fewer than 60% of at least ten decisions.
    Returns the keys tripped now."""
    from app.governance.breakers import breaker_open, trip

    tripped = []
    for key, found in agreement(db, now).items():
        spec = MODELS[key]
        if spec.tier != "high" or not spec.fallback or found["rate"] is None or found["rate"] >= AGREEMENT_FLOOR:
            continue
        if breaker_open(db, key):
            continue
        trip(db, key, reason=f"People agreed with it in only {round(100 * found['rate'])}% of {found['decided']} "
                             f"decisions in the last {WINDOW_DAYS} days.", by="Monitoring", now=now)
        tripped.append(key)
    return tripped
