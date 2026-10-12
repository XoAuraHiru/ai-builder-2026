from datetime import date, datetime, time, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.ml.aml_model import FEATURES, AmlModel, feature_history, train_local
from app.models import (Account, AmlAlert, BankStatement, Instruction, Person, Posting, ReconMatch, StatementLine,
                        TradeOrder)
from app.services.aml import account_features, run_monitoring

TODAY = date(2026, 10, 12)
QUIET = AmlModel(centroids=[[0.0] * 6], means={f: 0.0 for f in FEATURES}, stds={f: 1.0 for f in FEATURES},
                 threshold=1e12, source="test", model_name="test", trained_at="2026-10-12")


def at(day: int, hour: int = 15) -> datetime:
    return datetime.combine(date(2026, 10, day), time(hour), tzinfo=timezone.utc)


@pytest.fixture()
def people(db):
    out = {}
    for n, (key, name, country) in enumerate([("arjun", "Arjun Mehta", "US"), ("sofia", "Sofia Rossi", "US"),
                                              ("grace", "Grace Li", "US"), ("noah", "Noah Williams", "US"),
                                              ("aisha", "Aisha Khan", "US"), ("plain", "Pat Plain", "US"),
                                              ("farid", "Farid Tehrani", "IR")], start=1):
        person = Person(kind="investor", full_name=name, email=f"{key}@example.test", country=country)
        db.add(person)
        db.flush()
        account = Account(person_id=person.id, number=f"ACC-{n:04d}", opened_on=date(2025, 1, 2), bank_last4="4471")
        db.add(account)
        db.flush()
        out[key] = account
    db.commit()
    return out


def subscribe(db, account, amount, day, fund="ATR-CASH", state="settled"):
    row = Instruction(account_id=account.id, fund_code=fund, type="subscribe", amount=Decimal(amount), state=state,
                      requested_at=at(day))
    db.add(row)
    db.flush()
    return row


def posting(db, account, kind, cash, day):
    row = Posting(account_id=account.id, instrument="ATR-CASH", instrument_type="fund", posting_type=kind,
                  units=Decimal("1") if kind == "subscription" else Decimal("-1"), cash=Decimal(cash),
                  price=Decimal("1"), value_date=date(2026, 10, day), reference=f"{kind}-{day}")
    db.add(row)
    db.flush()
    return row


def alerts_for(db, account):
    return {a.scenario: a for a in db.scalars(select(AmlAlert).where(AmlAlert.person_id == account.person_id)).all()}


def test_structuring_just_under_the_reporting_threshold(db, people):
    rows = [subscribe(db, people["arjun"], a, d) for a, d in (("9400", 6), ("9750", 8), ("9900", 10))]
    subscribe(db, people["plain"], "9500", 8)
    run_monitoring(db, TODAY, QUIET)
    alert = alerts_for(db, people["arjun"])["structuring"]
    assert alert.severity == "high" and [e["id"] for e in alert.evidence] == [r.id for r in rows]
    assert "$29,050.00" in alert.summary and alerts_for(db, people["plain"]) == {}


def test_money_in_and_straight_out_needs_a_large_inflow(db, people):
    ins = posting(db, people["sofia"], "subscription", "-45000", 3)
    out = posting(db, people["sofia"], "redemption", "42000", 9)
    posting(db, people["plain"], "subscription", "-1500", 3)
    posting(db, people["plain"], "redemption", "3000", 5)
    run_monitoring(db, TODAY, QUIET)
    alert = alerts_for(db, people["sofia"])["rapid_in_out"]
    assert [e["id"] for e in alert.evidence] == [ins.id, out.id] and "6 days later, 93%" in alert.summary
    assert alerts_for(db, people["plain"]) == {}


def test_a_payment_from_someone_else(db, people):
    sub = subscribe(db, people["grace"], "6000", 7, fund="ATR-INC")
    statement = BankStatement(filename="s.csv", mime_type="text/csv", sha256="d" * 64, size_bytes=1, source="csv",
                              uploaded_by=people["plain"].person_id, notes=[])
    db.add(statement)
    db.flush()
    line = StatementLine(statement_id=statement.id, line_no=1, value_date=date(2026, 10, 7), amount=Decimal("6000"),
                         description="ACH CREDIT MARCUS OKONKWO", remitter="Marcus Okonkwo", state="matched")
    db.add(line)
    db.flush()
    db.add(ReconMatch(line_ids=[line.id], instruction_ids=[sub.id], tier="unique_amount", confidence=0.85,
                      evidence=[], proposed_by="rules", state="accepted"))
    run_monitoring(db, TODAY, QUIET)
    alert = alerts_for(db, people["grace"])["third_party_funding"]
    assert "paid by Marcus Okonkwo" in alert.summary and {e["kind"] for e in alert.evidence} == {
        "instruction", "statement_line"}


def test_money_moving_between_accounts_that_share_a_bank_account(db, people):
    people["noah"].bank_index = people["aisha"].bank_index = "b" * 64
    out = posting(db, people["noah"], "redemption", "8000", 4)
    into = subscribe(db, people["aisha"], "8000", 8)
    run_monitoring(db, TODAY, QUIET)
    alert = alerts_for(db, people["aisha"])["linked_round_trip"]
    assert [e["id"] for e in alert.evidence][:2] == [out.id, into.id] and "4 days later" in alert.summary


def test_velocity_and_high_risk_jurisdiction(db, people):
    for hour in range(5):
        db.add(TradeOrder(account_id=people["plain"].id, symbol="KO", side="buy", order_type="market", quantity=1,
                          state="filled", verdict="proceed", guardian={}, estimated_value=Decimal("60"),
                          broker="atrium-paper", trust_score=100, trust_band="clear", timeline=[],
                          created_at=at(11, 10 + hour)))
    subscribe(db, people["farid"], "2000", 9)
    run_monitoring(db, TODAY, QUIET)
    assert set(alerts_for(db, people["plain"])) == {"velocity"}
    assert set(alerts_for(db, people["farid"])) == {"high_risk_jurisdiction"}


def test_monitoring_raises_each_alert_once(db, people):
    for a, d in (("9400", 6), ("9750", 8), ("9900", 10)):
        subscribe(db, people["arjun"], a, d)
    assert len(run_monitoring(db, TODAY, QUIET)) == 1
    assert run_monitoring(db, TODAY, QUIET) == []


def test_the_anomaly_model_flags_unusual_accounts_only(db, people):
    model = AmlModel(centroids=[[0.0] * 6], means={f: 0.0 for f in FEATURES},
                     stds={"inflow_usd": 10000.0, "outflow_usd": 10000.0, "n_instructions": 5.0, "n_orders": 5.0,
                           "max_single_usd": 10000.0, "distinct_payers": 1.0},
                     threshold=3.0, source="test", model_name="test", trained_at="2026-10-12")
    subscribe(db, people["plain"], "1500", 5)
    subscribe(db, people["sofia"], "45000", 3)
    posting(db, people["sofia"], "redemption", "42000", 9)
    features = account_features(db, people["sofia"], TODAY)
    assert features["inflow_usd"] == 45000.0 and features["outflow_usd"] == 42000.0
    run_monitoring(db, TODAY, model)
    assert "anomaly" in alerts_for(db, people["sofia"]) and "anomaly" not in alerts_for(db, people["plain"])


def test_the_local_model_learns_ordinary_behaviour():
    model = train_local(feature_history(600), k=4)
    assert len(model.centroids) == 4 and model.threshold > 0
    ordinary = {"inflow_usd": 4500, "outflow_usd": 0, "n_instructions": 6, "n_orders": 0, "max_single_usd": 1500,
                "distinct_payers": 1}
    extreme = {**ordinary, "inflow_usd": 90000, "outflow_usd": 85000, "max_single_usd": 85000}
    assert model.distance(ordinary) < model.threshold < model.distance(extreme)
