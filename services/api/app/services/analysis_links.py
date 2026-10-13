"""Linking an investment to the analyzer run it came from. The link is an audit trail, so it must be honest: the same
kind of investment, the same fund or symbol, and an analysis the investor made themselves or made before signing in
(an anonymous one). A monthly plan only links to a unit-trust analysis that had a monthly amount."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Analysis


class AnalysisLinkError(ValueError):
    """The analysis cannot be linked to this investment; the message says why."""


def check_link(db: Session, analysis_id: str | None, *, kind: str, code: str, person_id: str | None,
               monthly: bool = False) -> str | None:
    if not analysis_id:
        return None
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise AnalysisLinkError("That analysis was not found; run it again from the front page.")
    if analysis.person_id and analysis.person_id != person_id:
        raise AnalysisLinkError("That analysis belongs to someone else.")
    if analysis.kind != kind or analysis.code != code:
        raise AnalysisLinkError(f"That analysis was for {analysis.name}, not this investment.")
    if monthly and not analysis.monthly_usd:
        raise AnalysisLinkError("That analysis had no monthly amount, so it cannot start a monthly plan.")
    return analysis.id
