from datetime import date, datetime, timezone
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import select

from app.ai.offline import offline_llm
from app.ml.aml_model import FEATURES, AmlModel
from app.models import AIDecision, Fund, Instruction, OpsRun, Price
from app.ops.day_end import run_day_end
from app.seed.funds import all_tickers, seed_funds
from app.services.pricing import publish_prices

PREV, AS_OF = date(2026, 10, 8), date(2026, 10, 9)
NOW = datetime(2026, 10, 9, 21, tzinfo=timezone.utc)   # Friday, 17:00 in New York
QUIET = AmlModel(centroids=[[0.0] * 6], means={f: 0.0 for f in FEATURES}, stds={f: 1.0 for f in FEATURES},
                 threshold=1e12, source="test", model_name="test", trained_at="2026-10-09")


@pytest.fixture()
def priced(db):
    seed_funds(db)
    for code in db.scalars(select(Fund.code)).all():
        publish_prices(db, code, pd.Series([100.0], index=pd.to_datetime([PREV])), Decimal("1000"))
    db.commit()


def closes(present=True):
    frame = pd.DataFrame({t: [100.0, 101.0] for t in all_tickers()}, index=pd.to_datetime([PREV, AS_OF]))
    if not present:
        frame = frame.iloc[:1]
    return frame


def test_a_run_drafts_prices_waits_to_allocate_and_writes_a_brief(db, priced, account):
    db.add(Instruction(account_id=account.id, fund_code="ATR-BAL", type="subscribe", amount=Decimal("1000"),
                       state="accepted", requested_at=datetime(2026, 10, 9, 14, tzinfo=timezone.utc)))
    run = run_day_end(db, now=NOW, triggered_by="test", llm=offline_llm(), closes=closes(), model=QUIET)
    steps = {s["step"]: s for s in run.steps}
    assert list(steps) == ["Prices", "Monthly plans", "Allocation", "Monitoring", "Exceptions", "Morning brief"]
    assert run.as_of == AS_OF and run.status == "ok" and steps["Prices"]["facts"]["drafted"] == 7
    assert "waiting" in steps["Allocation"]["detail"].lower() and "1 subscription" in steps["Exceptions"]["detail"]
    assert run.summary["headline"] and db.scalar(select(OpsRun.id)) == run.id
    assert db.scalars(select(AIDecision.purpose)).all() == ["ops_brief"]


def test_a_second_run_the_same_day_repeats_nothing(db, priced):
    run_day_end(db, now=NOW, triggered_by="test", llm=offline_llm(), closes=closes(), model=QUIET)
    again = run_day_end(db, now=NOW, triggered_by="test", llm=offline_llm(), closes=closes(), model=QUIET)
    prices = {s["step"]: s for s in again.steps}["Prices"]
    assert prices["facts"]["drafted"] == 0 and "waiting for approval" in prices["detail"]
    assert len(db.scalars(select(Price).where(Price.as_of == AS_OF)).all()) == 7


def test_missing_closes_make_a_partial_run_that_says_why(db, priced):
    run = run_day_end(db, now=NOW, triggered_by="test", llm=offline_llm(), closes=closes(present=False), model=QUIET)
    prices = {s["step"]: s for s in run.steps}["Prices"]
    assert run.status == "partial" and not prices["ok"] and "No closing prices yet" in prices["detail"]
