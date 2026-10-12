from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm import LLM, LLMError, get_llm
from app.auth import CurrentUser, get_current_user
from app.db import get_db
from app.models import Fund, Person
from app.schemas.invest import ExplainedWhatIf, WhatIfIn, WhatIfOut
from app.services.narrative import write_narrative
from app.services.whatif import Plan, WhatIfError, simulate

router = APIRouter(prefix="/invest", tags=["invest"])

EXPLAIN_BUSY = "The AI explanation is unavailable right now; the figures above are complete. Try again in a minute."
WHATIF_TASK = ("Explain what this what-if simulation means for the reader: the likely range of outcomes, how the "
               "scenarios compare, the chance of reaching their goal if they set one, the chance of ending with less "
               "than they paid in, and what fees cost over the period. Mention the history window and the worst 12 "
               "months it contains.")


def all_funds(db: Session) -> dict[str, Fund]:
    return {f.code: f for f in db.scalars(select(Fund)).all()}


def run_what_if(db: Session, body: WhatIfIn) -> WhatIfOut:
    funds = all_funds(db)
    scenarios = []
    for s in body.scenarios:
        only = next(iter(s.allocation)) if len(s.allocation) == 1 else None
        label = s.label or (funds[only].name if only in funds else "Custom mix")
        scenarios.append((label, dict(s.allocation)))
    try:
        result = simulate(funds, scenarios, Plan(body.initial_usd, body.monthly_usd, body.years, body.goal_usd))
    except WhatIfError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    method = (f"{result.paths:,} simulated paths, each stitched from 12-month blocks of real monthly returns between "
              f"{result.window_start} and {result.window_end}. The Atrium fee is deducted monthly; ETF costs are "
              f"already in the prices. A simulation, not a forecast.")
    return WhatIfOut(initial_usd=body.initial_usd, monthly_usd=body.monthly_usd, years=body.years,
                     goal_usd=body.goal_usd, contributed=result.contributed, window_start=result.window_start,
                     window_end=result.window_end, months=result.months, paths=result.paths, method=method,
                     scenarios=[asdict(s) for s in result.scenarios])


def whatif_facts(out: WhatIfOut, risk_band: int | None) -> dict:
    return {
        "plan": {"starting_amount_usd": round(out.initial_usd), "monthly_usd": round(out.monthly_usd),
                 "years": out.years, "goal_usd": round(out.goal_usd) if out.goal_usd else None,
                 "total_paid_in_usd": round(out.contributed)},
        "history_window": f"{out.window_start} to {out.window_end}", "simulated_paths": out.paths,
        "reader_risk_band": risk_band,
        "scenarios": [{
            "name": s.label, "annual_fee_pct": round(s.fee_bps / 100, 2),
            "median_outcome_usd": round(s.final["p50"]), "lower_10pct_outcome_usd": round(s.final["p10"]),
            "upper_10pct_outcome_usd": round(s.final["p90"]), "chance_of_goal_pct": s.prob_goal,
            "chance_below_paid_in_pct": s.prob_loss, "fees_cost_over_period_usd": round(s.fee_cost),
            "historical_annual_return_pct": s.history["annual_return_pct"],
            "historical_volatility_pct": s.history["annual_volatility_pct"],
            "worst_12_months_pct": s.history["worst_12m_pct"], "best_12_months_pct": s.history["best_12m_pct"],
            "max_drawdown_pct": s.history["max_drawdown_pct"]} for s in out.scenarios],
    }


@router.post("/what-if", response_model=WhatIfOut)
def what_if(body: WhatIfIn, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    return run_what_if(db, body)


@router.post("/what-if/explain", response_model=ExplainedWhatIf)
def explain_what_if(body: WhatIfIn, db: Session = Depends(get_db), llm: LLM = Depends(get_llm),
                    user: CurrentUser = Depends(get_current_user)):
    out = run_what_if(db, body)
    person = db.get(Person, user.person_id) if user.person_id else None
    try:
        narrative = write_narrative(
            db, llm, purpose="whatif_narrative", agent="investor_copilot", task=WHATIF_TASK, audience="an investor",
            facts=whatif_facts(out, person.risk_band if person else None), subject_type="person",
            subject_id=user.person_id or user.uid)
    except LLMError as e:
        raise HTTPException(status_code=503, detail=EXPLAIN_BUSY) from e
    db.commit()
    return ExplainedWhatIf(result=out, narrative=narrative)
