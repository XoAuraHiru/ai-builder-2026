from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import select

from app.models import Account, AmlAlert, Fund, Person, ReconMatch
from app.seed.funds import seed_funds
from app.seed.operations import seed_operations, seed_waiting
from app.services.blind_index import blind_index
from app.services.ledger import apply_posting
from app.services.pricing import publish_prices
from app.services.reconciliation import open_receipts

TODAY = date(2026, 10, 12)
INVESTORS = ["priya", "lucas", "hana", "tom", "sofia", "arjun", "grace", "noah", "aisha"]


@pytest.fixture()
def world(db):
    seed_funds(db)
    days = pd.bdate_range(TODAY - timedelta(days=40), TODAY)
    for code in db.scalars(select(Fund.code)).all():
        publish_prices(db, code, pd.Series([100.0] * len(days), index=days), Decimal("1000000"))
    out = {}
    for n, key in enumerate(INVESTORS, start=1):
        person = Person(kind="investor", full_name=f"{key.title()} Test", email=f"{key}@atrium.demo", risk_band=3)
        db.add(person)
        db.flush()
        out[key] = Account(person_id=person.id, number=f"ACC-{n:04d}", opened_on=date(2024, 10, 1),
                           bank_last4=f"{1000 + n}")
        db.add(out[key])
    for email, kind in (("mei@atrium.demo", "ops"), ("omar@atrium.demo", "compliance"),
                        ("daniel@atrium.demo", "advisor")):
        db.add(Person(kind=kind, full_name=email.split("@")[0].title(), email=email))
    db.flush()
    apply_posting(db, account_id=out["noah"].id, instrument="ATR-CASH", instrument_type="fund",
                  posting_type="subscription", units=Decimal("200"), cash=Decimal("-20000"), price=Decimal("100"),
                  value_date=date(2025, 1, 2), reference="SEED")
    db.commit()
    return out


def test_the_seed_adds_a_checker_codes_links_receipts_and_stories(db, world):
    assert seed_operations(db, TODAY) is True
    sam = db.scalar(select(Person).where(Person.email == "sam@atrium.demo"))
    assert sam.kind == "ops" and sam.totp_secret
    assert all(p.totp_secret for p in db.scalars(select(Person).where(Person.kind != "investor")).all())
    assert world["noah"].bank_index == world["aisha"].bank_index and world["aisha"].bank_last4 == world["noah"].bank_last4
    indexes = [a.bank_index for a in db.scalars(select(Account)).all()]
    assert all(indexes) and len(set(indexes)) == len(indexes) - 1
    assert len(open_receipts(db)) == 6
    scenarios = {(a.scenario, a.person_id) for a in db.scalars(select(AmlAlert)).all()}
    assert {("structuring", world["arjun"].person_id), ("rapid_in_out", world["sofia"].person_id),
            ("third_party_funding", world["grace"].person_id),
            ("linked_round_trip", world["aisha"].person_id)} <= scenarios
    assert db.scalar(select(ReconMatch.state)) == "accepted"
    assert seed_operations(db, TODAY) is False
    assert len(seed_waiting(db)) == 6 and len(open_receipts(db)) == 12  # the persona demo can add another set


def test_the_blind_index_is_keyed_and_ignores_formatting():
    assert blind_index("0001-8452 7781") == blind_index("000184527781") and len(blind_index("1")) == 64
    assert blind_index("000184527781") != blind_index("000184527782")
