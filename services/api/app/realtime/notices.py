"""What each event tells whom. A notice is raised beside the domain event it reports; it costs nothing while the inbox
is off and never fails the work it reports on.

Leads are the one exception. Their trust band is set wherever new evidence arrives (scoring, an identity document, a
call, a ring flag), so the inbox watches the band as it is written rather than being called from the Trust Score's
code, which stays exactly as it was validated.
"""
from __future__ import annotations

import functools
import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from app.governance.inventory import MODELS
from app.models import Account, AmlAlert, Approval, Lead, ModelBreaker, OpsRun, Person, TradeOrder
from app.realtime.inbox import Item, courier, notify, people

if TYPE_CHECKING:  # the services import this module, so their types are named, not imported
    from app.services.guardian import GuardianReport

log = logging.getLogger(__name__)

ADVISORS, OPERATIONS, COMPLIANCE = ("advisor",), ("ops",), ("compliance",)
ALERT_SEVERITY = {"high": "urgent", "medium": "attention", "low": "info"}
HELD_LEADS = {"blocked": ("lead_blocked", "Lead blocked", "urgent"),
              "high_risk": ("lead_held", "Lead held for review", "attention")}


def notice(build):
    """Does nothing while the inbox is off; a notice that cannot be put together is logged, never raised."""
    @functools.wraps(build)
    def raise_notice(db: Session, *args, **kwargs) -> None:
        if courier() is None:
            return
        try:
            build(db, *args, **kwargs)
        except Exception:
            log.exception("inbox: %s skipped", build.__name__)

    return raise_notice


def first_name(name: str) -> str:
    return name.split()[0] if name.split() else name


def clip(text: str, limit: int = 280) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def listed(words: list[str]) -> str:
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def usd(x) -> str:
    return f"${Decimal(x):,.2f}"


def _holder(db: Session, order: TradeOrder) -> str:
    return db.get(Account, order.account_id).person_id


# Trade

@notice
def order_held(db: Session, order: TradeOrder, report: GuardianReport) -> None:
    """The Guardian held an order: every advisor, since any of them may review it."""
    client = db.get(Account, order.account_id).person.full_name
    deal = f"{'purchase' if order.side == 'buy' else 'sale'} of {order.quantity} {order.symbol}"
    if report.takeover:
        why = ("Possible account takeover: a large sale from a device first seen within a day. "
               f"Trust score {report.trust.score} of 100.")
    else:
        reasons = [f"account trust (score {report.trust.score} of 100)" if c.code == "TRUST" else c.title.lower()
                   for c in report.checks if c.outcome == "hold"]
        why = f"Held for an advisor's review: {listed(reasons)}."
    notify(db, people(db, *ADVISORS), Item(
        kind="order_held", source_id=order.id, stage="trade", title=f"{client}'s {deal} is held", body=why,
        href="/advisor/held", severity="urgent" if report.takeover else "attention", actor="Pre-trade Guardian"))


@notice
def order_released(db: Session, order: TradeOrder, advisor: Person) -> None:
    """An advisor let a held order go: the account holder, with where it stands now."""
    from app.services.orders import describe  # orders imports this module

    outcome = {"filled": f"Filled at {usd(order.fill_price)} a share.",
               "open": "It is with the broker, waiting for its price."}.get(order.state, "The broker turned it down.")
    note = f" {first_name(advisor.full_name)}'s note: {order.review_note}" if order.review_note else ""
    notify(db, [_holder(db, order)], Item(
        kind="order_released", source_id=order.id, stage="trade",
        title=f"{first_name(advisor.full_name)} released your order", body=clip(f"{describe(order)}. {outcome}{note}"),
        href="/investor/trades", severity="attention" if order.state == "rejected" else "info",
        actor=advisor.full_name))


@notice
def order_rejected(db: Session, order: TradeOrder, advisor: Person) -> None:
    """An advisor turned a held order down: the account holder, with the advisor's reason."""
    from app.services.orders import describe

    reason = f": {clip(order.review_note, 100)}" if order.review_note else ""
    notify(db, [_holder(db, order)], Item(
        kind="order_rejected", source_id=order.id, stage="trade",
        title=f"{first_name(advisor.full_name)} rejected your order{reason}",
        body=f"{describe(order)}. Nothing was sent to the market.", href="/investor/trades", severity="attention",
        actor=advisor.full_name))


# Operate

@notice
def approval_requested(db: Session, approval: Approval, requester: Person, approvers: tuple[str, ...]) -> None:
    """A four-eyes request: everyone who may approve it, never the person asking."""
    notify(db, people(db, *approvers, besides=[requester.id]), Item(
        kind="approval_requested", source_id=approval.id, stage="operate",
        title=f"{first_name(requester.full_name)} asks for your approval",
        body=clip(f"{approval.summary}. Reason: {approval.reason}"), href="/operations/approvals",
        severity="attention", actor=requester.full_name))


@notice
def approval_decided(db: Session, approval: Approval, approver: Person) -> None:
    """A decided request: the person who asked."""
    verdict = "approved" if approval.state == "approved" else "rejected"
    note = f" Note: {approval.decision_note}" if approval.decision_note else ""
    notify(db, [approval.requested_by], Item(
        kind="approval_decided", source_id=approval.id, stage="operate",
        title=f"{first_name(approver.full_name)} {verdict} your request", body=clip(f"{approval.summary}.{note}"),
        href="/operations/approvals", severity="info" if verdict == "approved" else "attention",
        actor=approver.full_name))


@notice
def day_end_finished(db: Session, run: OpsRun) -> None:
    """A finished day-end: operations, in one line."""
    facts = {s["step"]: s.get("facts") or {} for s in run.steps}
    counts = [(facts.get("Prices", {}).get("drafted", 0), "fund price", "drafted"),
              (len(facts.get("Monitoring", {}).get("alerts", [])), "new alert", "for compliance"),
              (facts.get("Exceptions", {}).get("approvals", 0), "approval", "waiting"),
              (facts.get("Exceptions", {}).get("unmatched_lines", 0), "statement line", "unmatched")]
    parts = [f"{plural(n, word)} {tail}" for n, word, tail in counts if n]
    line = f"{listed(parts) if parts else 'Nothing is waiting for operations'}."
    look = [s["step"].lower() for s in run.steps if not s["ok"]]
    if look:
        line += f" To look at: {listed(look)}."
    when = f" for {run.as_of:%B} {run.as_of.day}" if run.as_of else ""
    notify(db, people(db, *OPERATIONS), Item(
        kind="day_end", source_id=run.id, stage="operate",
        title=f"Day-end{when} finished" + ("" if run.status == "ok" else " with steps to look at"), body=line,
        href="/operations", severity="info" if run.status == "ok" else "attention", actor="Day-end"))


# Govern

@notice
def alerts_raised(db: Session, alerts: list[AmlAlert], *, actor: str, besides: str | None = None) -> None:
    """New AML alerts: compliance, one notice each, less the person whose action raised them."""
    if not alerts:
        return
    to = people(db, *COMPLIANCE, besides=[besides])
    for alert in alerts:
        holder = db.get(Person, alert.person_id).full_name
        notify(db, to, Item(
            kind="alert_raised", source_id=alert.id, stage="govern", title=f"{alert.title}: {holder}",
            body=clip(alert.summary), href=f"/compliance/alerts/{alert.id}",
            severity=ALERT_SEVERITY.get(alert.severity, "attention"), actor=actor))


@notice
def model_paused(db: Session, breaker: ModelBreaker, *, besides: str | None = None) -> None:
    """A circuit breaker opened: compliance and the model's owner, less whoever paused it by hand."""
    spec = MODELS[breaker.model_key]
    owner = db.scalar(select(Person.id).where(Person.email == spec.owner))
    to = [*people(db, *COMPLIANCE, besides=[besides]), *([owner] if owner and owner != besides else [])]
    stands_in = spec.fallback or "Nothing stands in for it until it is reset."
    notify(db, to, Item(
        kind="model_paused", source_id=f"{breaker.model_key}-{len(breaker.history or [])}", stage="govern",
        title=f"{spec.name} is paused", body=clip(f"{breaker.reason} {stands_in}"),
        href=f"/compliance/models/{breaker.model_key}", severity="attention", actor=breaker.changed_by))


# Acquire

@notice
def lead_trust_changed(db: Session, lead: Lead, before: str | None) -> None:
    """A lead's trust checks now stop its conversion (high risk or blocked): every advisor. A blocked lead easing to
    high risk is not news."""
    band = lead.trust_band
    if band not in HELD_LEADS or band == before or (band == "high_risk" and before == "blocked"):
        return
    kind, label, severity = HELD_LEADS[band]
    signals = sorted(lead.trust_signals or [], key=lambda s: (not s.get("blocking"), s.get("weight", 0)))
    found = listed([s["label"][:1].lower() + s["label"][1:] for s in signals[:3]]) if signals else "no single signal"
    notify(db, people(db, *ADVISORS), Item(
        kind=kind, source_id=lead.id, stage="acquire", title=f"{label}: {lead.full_name}",
        body=f"Trust score {lead.trust_score} of 100: {found}.", href=f"/advisor/leads/{lead.id}", severity=severity,
        actor="Trust Score"))


@event.listens_for(Session, "after_flush")
def _watch_lead_bands(session: Session, _flush_context) -> None:
    """After each flush (attribute history still holds the old band), note every lead whose band was written."""
    if courier() is None:
        return
    try:
        for lead in [o for o in (*session.new, *session.dirty) if isinstance(o, Lead)]:
            history = inspect(lead).attrs.trust_band.history
            if history.added:
                lead_trust_changed(session, lead, history.deleted[0] if history.deleted else None)
    except Exception:
        log.exception("inbox: lead watch skipped")
