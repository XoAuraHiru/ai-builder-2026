from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import Account, Fund, FundConstituent, Person, Price


def test_person_account_fund_price_round_trip(db):
    person = Person(kind="investor", full_name="Priya Raman", email="priya@example.test", country="US")
    db.add(person)
    db.flush()
    account = Account(person_id=person.id, number="ACC-0001", opened_on=date(2026, 1, 5))
    fund = Fund(
        code="ATR-BAL", name="Atrium Balanced", category="balanced", risk_band=3, fee_bps=35,
        min_investment=Decimal("500"), objective="Balanced growth and income.",
        who_for="Medium horizons, moderate tolerance.", inception_on=date(2024, 10, 1),
    )
    fund.constituents = [
        FundConstituent(ticker="VTI", weight=Decimal("0.6"), asset_class="equity", region="US", sector="broad"),
        FundConstituent(ticker="BND", weight=Decimal("0.4"), asset_class="bond", region="US", sector="aggregate"),
    ]
    db.add_all([account, fund])
    db.flush()
    db.add(Price(fund_code="ATR-BAL", as_of=date(2026, 1, 5), nav=Decimal("112.345678"),
                 units_in_issue=Decimal("1000000"), status="published"))
    db.commit()

    loaded = db.scalar(select(Fund).where(Fund.code == "ATR-BAL"))
    assert loaded is not None
    assert [c.ticker for c in loaded.constituents] == ["VTI", "BND"]
    assert sum(c.weight for c in loaded.constituents) == Decimal("1.0")
    assert db.scalar(select(Account).where(Account.number == "ACC-0001")).person_id == person.id
    assert db.scalar(select(Price)).nav == Decimal("112.345678")
    assert account.base_currency == "USD"
    assert account.status == "active"
    assert person.id and len(person.id) == 32
