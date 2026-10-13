"""The public return analyzer (front door). Anyone may run it; each run is saved and counted against an hourly limit
per device or network and overall, before any simulation. The explanation is Gemini, so it is for signed-in people
only: visitors get the figures and the charts, which need no AI."""
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ai.llm import LLM, LLMError, get_llm
from app.auth import CurrentUser, get_current_user, optional_user
from app.config import get_settings
from app.db import get_db
from app.models import Analysis, Person
from app.models.base import utcnow
from app.routers.invest import EXPLAIN_BUSY, all_funds, what_if_out, whatif_facts
from app.schemas.analyzer import AnalysisOut, AnalyzeIn, AnalyzerOptions, ExplainedAnalysis
from app.services.analyzer import (MIN_SHARE_MONTHS, AnalysisRequest, AnalysisResult, AnalyzerError, analyze,
                                   share_options)
from app.services.capture_guard import ip_hash
from app.services.instructions import RECURRING_MINIMUM
from app.services.narrative import write_narrative

router = APIRouter(prefix="/analyzer", tags=["analyzer"])

TASK = ("Explain what this simulation means for someone deciding whether to invest: the likely range of outcomes, the "
        "chance of ending with less than they paid in, and, if there is a second scenario, how the investment compares "
        "with it. Mention the history window and the worst 12 months it contains. If the investment is a single share, "
        "say plainly that one company's past is no guide to its future and that the list of shares was chosen today.")


def method_text(a: AnalysisResult) -> str:
    r = a.result
    base = (f"{r.paths:,} simulated paths, each stitched from 12-month blocks of real monthly returns between "
            f"{r.window_start} and {r.window_end}.")
    if a.kind == "unit_trust":
        return f"{base} The fund's {a.fee_bps / 100:.2f}% annual fee is deducted monthly. A simulation, not a forecast."
    return (f"{base} The S&P 500 is simulated on the same months for comparison. No fund fee applies; trading costs and "
            "taxes are not included. A simulation, not a forecast.")


def analysis_out(row: Analysis, a: AnalysisResult) -> AnalysisOut:
    return AnalysisOut(id=row.id, kind=a.kind, code=a.code, name=a.name, fee_bps=a.fee_bps,
                       min_investment=a.min_investment, result=what_if_out(a.result, method_text(a)),
                       comparison=asdict(a.comparison) if a.comparison else None)


def summary_of(a: AnalysisResult) -> dict:
    s = a.result.scenarios[0]
    return {"median_usd": s.final["p50"], "p10_usd": s.final["p10"], "p90_usd": s.final["p90"],
            "contributed_usd": a.result.contributed, "prob_loss_pct": s.prob_loss,
            "window_start": a.result.window_start, "window_end": a.result.window_end,
            "comparison_median_usd": a.comparison.final["p50"] if a.comparison else None}


def check_rate(db: Session, device_id: str, ip: str) -> None:
    settings = get_settings()
    since = utcnow() - timedelta(hours=1)
    mine = db.scalar(select(func.count()).select_from(Analysis).where(
        Analysis.created_at >= since, or_(Analysis.device_id == device_id, Analysis.ip_hash == ip)))
    if (mine or 0) >= settings.analyzer_limit_per_hour:
        raise HTTPException(status_code=429,
                            detail="You've run many analyses in the last hour; please try again later.")
    total = db.scalar(select(func.count()).select_from(Analysis).where(Analysis.created_at >= since))
    if (total or 0) >= settings.analyzer_global_per_hour:
        raise HTTPException(status_code=429, detail="The analyzer is busy right now; please try again later.")


def rerun(db: Session, row: Analysis) -> AnalysisResult:
    req = AnalysisRequest(kind=row.kind, code=row.code, initial_usd=float(row.initial_usd),
                          monthly_usd=float(row.monthly_usd), years=row.years)
    return analyze(all_funds(db), req)


@router.get("/options", response_model=AnalyzerOptions)
def options(db: Session = Depends(get_db)):
    funds = sorted(all_funds(db).values(), key=lambda f: (f.risk_band, f.name))
    return AnalyzerOptions(
        funds=[{"code": f.code, "name": f.name, "risk_band": f.risk_band, "fee_bps": f.fee_bps,
                "min_investment": float(f.min_investment)} for f in funds],
        shares=share_options(), min_share_years=MIN_SHARE_MONTHS // 12, monthly_minimum=float(RECURRING_MINIMUM))


@router.post("", response_model=AnalysisOut, status_code=201)
def run(body: AnalyzeIn, request: Request, db: Session = Depends(get_db),
        user: CurrentUser | None = Depends(optional_user)):
    ip = ip_hash(request)
    check_rate(db, body.device_id, ip)
    req = AnalysisRequest(kind=body.kind, code=body.code.strip().upper() if body.kind == "share" else body.code.strip(),
                          initial_usd=body.initial_usd, monthly_usd=body.monthly_usd, years=body.years)
    try:
        a = analyze(all_funds(db), req)
    except AnalyzerError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    row = Analysis(kind=a.kind, code=a.code, name=a.name, initial_usd=Decimal(str(body.initial_usd)),
                   monthly_usd=Decimal(str(body.monthly_usd)), years=body.years, summary=summary_of(a),
                   person_id=user.person_id if user else None, device_id=body.device_id, ip_hash=ip)
    db.add(row)
    db.commit()
    return analysis_out(row, a)


@router.post("/{analysis_id}/explain", response_model=ExplainedAnalysis)
def explain(analysis_id: str, db: Session = Depends(get_db), llm: LLM = Depends(get_llm),
            user: CurrentUser = Depends(get_current_user)):
    row = db.get(Analysis, analysis_id)
    if row is None or (row.person_id and row.person_id != user.person_id):
        raise HTTPException(status_code=404, detail="That analysis was not found.")
    a = rerun(db, row)
    out = analysis_out(row, a)
    if a.comparison:
        out.result.scenarios.append(out.comparison)
    person = db.get(Person, user.person_id) if user.person_id else None
    try:
        narrative = write_narrative(
            db, llm, purpose="analyzer_narrative", agent="investor_copilot", task=TASK, audience="a possible investor",
            facts=whatif_facts(out.result, person.risk_band if person else None), subject_type="analysis",
            subject_id=row.id)
    except LLMError as e:
        raise HTTPException(status_code=503, detail=EXPLAIN_BUSY) from e
    db.commit()
    return ExplainedAnalysis(narrative=narrative)
