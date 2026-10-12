from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Lot, Posting
from app.services.ledger import InsufficientUnits, apply_posting, balance, holdings, q_cash, q_units


def sub(db, account, units, cash, price, day, ref):
    return apply_posting(
        db, account_id=account.id, instrument="ATR-BAL", instrument_type="fund", posting_type="subscription",
        units=Decimal(units), cash=Decimal(cash), price=Decimal(price), value_date=day, reference=ref,
    )


def test_subscription_opens_lot_and_balance(db, account):
    sub(db, account, "81.012345", "-10000.00", "123.438100", date(2026, 1, 5), "SUB-1")
    assert balance(db, account.id, "ATR-BAL") == Decimal("81.012345")
    h = holdings(db, account.id)
    assert len(h) == 1
    assert h[0].instrument == "ATR-BAL"
    assert h[0].units == Decimal("81.012345")
    assert h[0].cost_basis == q_cash(Decimal("81.012345") * Decimal("123.438100"))
    lots = db.scalars(select(Lot)).all()
    assert len(lots) == 1 and lots[0].units_remaining == Decimal("81.012345")


def test_redemption_consumes_lots_fifo_and_records_realised_cost(db, account):
    sub(db, account, "100", "-1000.00", "10", date(2026, 1, 1), "SUB-1")
    sub(db, account, "100", "-1200.00", "12", date(2026, 2, 1), "SUB-2")
    red = apply_posting(
        db, account_id=account.id, instrument="ATR-BAL", instrument_type="fund", posting_type="redemption",
        units=Decimal("-150"), cash=Decimal("2250.00"), price=Decimal("15"), value_date=date(2026, 3, 1), reference="RED-1",
    )
    assert red.realised_cost == Decimal("1600.00")  # 100 @ 10 + 50 @ 12
    lots = db.scalars(select(Lot).order_by(Lot.acquired_on)).all()
    assert [lot.units_remaining for lot in lots] == [Decimal("0"), Decimal("50")]
    assert balance(db, account.id, "ATR-BAL") == Decimal("50")
    assert holdings(db, account.id)[0].cost_basis == Decimal("600.00")


def test_redeeming_more_than_held_raises_and_writes_nothing(db, account):
    sub(db, account, "10", "-100.00", "10", date(2026, 1, 1), "SUB-1")
    db.commit()
    with pytest.raises(InsufficientUnits):
        apply_posting(
            db, account_id=account.id, instrument="ATR-BAL", instrument_type="fund", posting_type="redemption",
            units=Decimal("-10.000001"), cash=Decimal("100.00"), price=Decimal("10"), value_date=date(2026, 1, 2), reference="RED-X",
        )
    db.rollback()
    assert len(db.scalars(select(Posting)).all()) == 1
    assert balance(db, account.id, "ATR-BAL") == Decimal("10")


def test_quantisation_is_six_and_two_places_half_even():
    assert q_units(Decimal("1.0000005")) == Decimal("1.000000")
    assert q_units(Decimal("1.0000015")) == Decimal("1.000002")
    assert q_cash(Decimal("10.005")) == Decimal("10.00")
    assert q_cash(Decimal("10.015")) == Decimal("10.02")


def test_holdings_are_per_instrument_and_skip_zero_positions(db, account):
    sub(db, account, "5", "-500.00", "100", date(2026, 1, 1), "SUB-1")
    apply_posting(
        db, account_id=account.id, instrument="ATR-GRW", instrument_type="fund", posting_type="subscription",
        units=Decimal("2"), cash=Decimal("-300.00"), price=Decimal("150"), value_date=date(2026, 1, 1), reference="SUB-2",
    )
    apply_posting(
        db, account_id=account.id, instrument="ATR-BAL", instrument_type="fund", posting_type="redemption",
        units=Decimal("-5"), cash=Decimal("550.00"), price=Decimal("110"), value_date=date(2026, 1, 9), reference="RED-1",
    )
    h = holdings(db, account.id)
    assert [x.instrument for x in h] == ["ATR-GRW"]
