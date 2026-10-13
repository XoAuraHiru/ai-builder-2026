"""Lifecycle Trust Score, stage 1 (lead). Fixed rule weights keep the score reproducible; Gemini and Document AI
contribute evidence only. A rising risk adds friction or holds the lead; only a person blocks or converts."""
from dataclasses import asdict, dataclass, field
from datetime import timedelta

from sqlalchemy import false, func, or_, select
from sqlalchemy.orm import Session

from app.events import emit
from app.ml.lead_features import PHONE_RE
from app.models import IdentityCheck, Lead, Person, RingFlag

DISPOSABLE_DOMAINS = frozenset({
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com", "temp-mail.org", "yopmail.com",
    "trashmail.com", "sharklasers.com", "getnada.com", "dispostable.com", "maildrop.cc", "throwawaymail.com",
    "fakeinbox.com", "mintemail.com", "emailondeck.com", "mohmal.com", "burnermail.io", "spamgourmet.com",
    "tempr.email", "moakt.com"})
SEVERITY_WEIGHT = {"high": -15, "medium": -8, "low": -3}
CONSISTENCY_CAP = -25
ACTIONS = {"clear": "Proceed with onboarding.", "review": "Add friction: step-up verification or an advisor call.",
           "high_risk": "Hold for review before any onboarding.", "blocked": "Blocked pending human review."}


@dataclass(frozen=True)
class TrustSignal:
    code: str
    label: str
    weight: int
    evidence: str
    source: str
    blocking: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class TrustReport:
    score: int
    band: str
    signals: list[TrustSignal] = field(default_factory=list)
    blocked: bool = False

    @property
    def action(self) -> str:
        return ACTIONS[self.band]


def _contact_signals(db: Session, lead: Lead) -> list[TrustSignal]:
    out: list[TrustSignal] = []
    domain = lead.email.rsplit("@", 1)[-1].lower()
    if domain in DISPOSABLE_DOMAINS:
        out.append(TrustSignal("T01", "Disposable email domain", -25, f"{domain} is a throwaway mailbox provider", "rule"))
    if lead.phone and not PHONE_RE.match(lead.phone):
        out.append(TrustSignal("T02", "Phone not in international format", -10,
                               f"'{lead.phone}' is not in +<country><number> form", "rule"))
    elif lead.phone and lead.country == "US" and not lead.phone.startswith("+1"):
        out.append(TrustSignal("T03", "Phone country does not match", -5,
                               f"US applicant with a {lead.phone[:3]} phone number", "rule"))
    same_phone = (Lead.phone == lead.phone) if lead.phone else false()
    matches = db.scalars(select(Lead).where(
        Lead.id != lead.id, Lead.created_at >= lead.created_at - timedelta(days=90),
        or_(func.lower(Lead.email) == lead.email.lower(), same_phone)).order_by(Lead.created_at)).all()
    if matches:
        shared = "email" if any(m.email.lower() == lead.email.lower() for m in matches) else "phone"
        ids = ", ".join(m.id for m in matches[:3])
        out.append(TrustSignal("T04", "Contact shared with another lead", -25,
                               f"Shares its {shared} with {len(matches)} other lead(s): {ids}", "rule"))
    same_device = db.scalar(select(func.count()).select_from(Lead).where(
        Lead.id != lead.id, Lead.device_id == lead.device_id,
        Lead.created_at >= lead.created_at - timedelta(hours=24),
        Lead.created_at <= lead.created_at + timedelta(hours=24))) or 0
    if same_device >= 2:
        out.append(TrustSignal("T05", "Many leads from one device", -25,
                               f"{same_device + 1} leads from the same device within 24 hours", "rule"))
    return out


def _enrichment_signals(enrichment: dict | None) -> list[TrustSignal]:
    if not enrichment:
        return []
    out: list[TrustSignal] = []
    budget = CONSISTENCY_CAP
    for issue in enrichment.get("consistency_issues", []):
        weight = max(SEVERITY_WEIGHT[issue["severity"]], budget)
        if weight >= 0:
            break
        out.append(TrustSignal("T06", f"Inconsistent answers ({issue['severity']})", weight,
                               f"{issue['field']}: {issue['issue']}", "gemini"))
        budget -= weight
    authenticity = enrichment.get("text_authenticity")
    if authenticity == "likely_generated":
        out.append(TrustSignal("T07", "Free text looks machine-generated", -10,
                               "Goals and notes read as generated text", "gemini"))
    elif authenticity == "templated":
        out.append(TrustSignal("T07", "Free text looks templated", -5, "Goals and notes read as a template", "gemini"))
    return out


def _identity_signals(identity: IdentityCheck | None) -> list[TrustSignal]:
    if identity is None:
        return []
    return [TrustSignal(f["code"], f["label"], int(f["weight"]), f["evidence"], f["source"], bool(f.get("blocking")))
            for f in identity.findings]


def _ring_signals(db: Session, lead: Lead) -> list[TrustSignal]:
    """T09: a compliance person flagged the lead as part of a fraud ring (one signal, however many rings)."""
    flag = db.scalar(select(RingFlag).where(RingFlag.lead_id == lead.id).order_by(RingFlag.created_at).limit(1))
    if flag is None:
        return []
    who = db.get(Person, flag.flagged_by)
    day = flag.created_at
    return [TrustSignal("T09", "Part of a fraud ring", -25,
                        f"Flagged by {who.full_name if who else 'compliance'} on {day:%B} {day.day}, {day.year}",
                        "rings", False)]


def assess_trust(db: Session, lead: Lead, enrichment: dict | None, identity: IdentityCheck | None) -> TrustReport:
    signals = (_contact_signals(db, lead) + _enrichment_signals(enrichment) + _identity_signals(identity)
               + _ring_signals(db, lead))
    signals.sort(key=lambda s: (s.code[0] != "T", int(s.code[1:]), s.evidence))
    score = max(0, min(100, 100 + sum(s.weight for s in signals)))
    blocked = any(s.blocking for s in signals)
    return TrustReport(score=score, band=band_for(score, blocked), signals=signals, blocked=blocked)


def band_for(score: int, blocked: bool) -> str:
    return "blocked" if blocked else "clear" if score >= 80 else "review" if score >= 50 else "high_risk"


def band_without(signals: list[dict], codes: set[str]) -> str:
    """The band a lead's stored signals would give without some of them (the ring radar leaves out its own T09)."""
    kept = [s for s in signals if s.get("code") not in codes]
    score = max(0, min(100, 100 + sum(int(s.get("weight", 0)) for s in kept)))
    return band_for(score, any(s.get("blocking") for s in kept))


def latest_identity_check(db: Session, lead: Lead) -> IdentityCheck | None:
    return db.scalar(select(IdentityCheck).where(IdentityCheck.lead_id == lead.id)
                     .order_by(IdentityCheck.created_at.desc()).limit(1))


def apply_trust(db: Session, lead: Lead) -> TrustReport:
    report = assess_trust(db, lead, lead.enrichment, latest_identity_check(db, lead))
    previous = (lead.trust_score, lead.trust_band)
    lead.trust_score, lead.trust_band = report.score, report.band
    lead.trust_signals = [s.as_dict() for s in report.signals]
    if previous != (report.score, report.band):
        emit("TrustScoreChanged", {"lead_id": lead.id, "score": report.score, "band": report.band,
                                   "previous": {"score": previous[0], "band": previous[1]}})
    db.flush()
    return report
