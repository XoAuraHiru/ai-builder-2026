from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import INSTRUMENT_TYPES, POSTING_TYPES, Lot, Posting

UNITS_Q = Decimal("0.000001")
CASH_Q = Decimal("0.01")
ZERO = Decimal("0")


class LedgerError(Exception):
    pass


class InsufficientUnits(LedgerError):
    pass


def q_units(x: Decimal) -> Decimal:
    return Decimal(x).quantize(UNITS_Q, rounding=ROUND_HALF_EVEN)


def q_cash(x: Decimal) -> Decimal:
    return Decimal(x).quantize(CASH_Q, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True)
class Holding:
    instrument: str
    instrument_type: str
    units: Decimal
    cost_basis: Decimal


def balance(db: Session, account_id: str, instrument: str) -> Decimal:
    """Units held, summed from postings in exact decimal arithmetic."""
    units = db.scalars(
        select(Posting.units).where(Posting.account_id == account_id, Posting.instrument == instrument)
    ).all()
    return q_units(sum(units, ZERO))


def holdings(db: Session, account_id: str) -> list[Holding]:
    """Open positions from remaining FIFO lots, cross-checked against the postings."""
    lots = db.scalars(
        select(Lot).where(Lot.account_id == account_id, Lot.units_remaining > 0).order_by(Lot.instrument)
    ).all()
    units: dict[str, Decimal] = defaultdict(lambda: ZERO)
    cost: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for lot in lots:
        units[lot.instrument] += lot.units_remaining
        cost[lot.instrument] += lot.units_remaining * lot.cost_per_unit
    out: list[Holding] = []
    for instrument in sorted(units):
        held = q_units(units[instrument])
        if held <= 0:
            continue
        posted = balance(db, account_id, instrument)
        if posted != held:
            raise LedgerError(f"lot/posting mismatch for {instrument}: lots={held} postings={posted}")
        itype = db.scalar(
            select(Posting.instrument_type)
            .where(Posting.account_id == account_id, Posting.instrument == instrument)
            .limit(1)
        )
        out.append(Holding(instrument=instrument, instrument_type=itype or "fund", units=held,
                           cost_basis=q_cash(cost[instrument])))
    return out


def apply_posting(
    db: Session,
    *,
    account_id: str,
    instrument: str,
    instrument_type: str,
    posting_type: str,
    units: Decimal,
    cash: Decimal,
    price: Decimal,
    value_date: date,
    reference: str,
) -> Posting:
    """Append one posting. Positive units open a lot; negative units consume lots FIFO.

    Raises InsufficientUnits before anything is written if the account cannot cover a sale.
    Callers own the transaction: commit after a successful call, rollback on error.
    """
    if instrument_type not in INSTRUMENT_TYPES:
        raise LedgerError(f"unknown instrument_type {instrument_type!r}")
    if posting_type not in POSTING_TYPES:
        raise LedgerError(f"unknown posting_type {posting_type!r}")
    units = q_units(Decimal(units))
    cash = q_cash(Decimal(cash))
    price = Decimal(price)
    if units == 0 and cash == 0:
        raise LedgerError("a posting must move units or cash")

    realised_cost: Decimal | None = None
    if units < 0:
        consumed = _consume_fifo(db, account_id, instrument, -units)
        realised_cost = q_cash(sum((take * lot.cost_per_unit for lot, take in consumed), ZERO))

    posting = Posting(
        account_id=account_id, instrument=instrument, instrument_type=instrument_type, posting_type=posting_type,
        units=units, cash=cash, price=price, realised_cost=realised_cost, value_date=value_date, reference=reference,
    )
    db.add(posting)
    db.flush()
    if units > 0:
        db.add(Lot(
            account_id=account_id, instrument=instrument, units_initial=units, units_remaining=units,
            cost_per_unit=price, acquired_on=value_date, posting_id=posting.id,
        ))
        db.flush()
    return posting


def _consume_fifo(db: Session, account_id: str, instrument: str, units_to_sell: Decimal) -> list[tuple[Lot, Decimal]]:
    lots = db.scalars(
        select(Lot)
        .where(Lot.account_id == account_id, Lot.instrument == instrument, Lot.units_remaining > 0)
        .order_by(Lot.acquired_on, Lot.created_at)
    ).all()
    available = q_units(sum((lot.units_remaining for lot in lots), ZERO))
    if available < units_to_sell:
        raise InsufficientUnits(f"{instrument}: holding {available}, requested {units_to_sell}")
    remaining = units_to_sell
    consumed: list[tuple[Lot, Decimal]] = []
    for lot in lots:
        if remaining <= 0:
            break
        take = min(lot.units_remaining, remaining)
        lot.units_remaining = q_units(lot.units_remaining - take)
        remaining = q_units(remaining - take)
        consumed.append((lot, take))
    return consumed
