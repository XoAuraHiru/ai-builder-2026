from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fund
from app.services.ledger import holdings, q_cash
from app.services.pricing import latest_price


class PriceUnavailable(Exception):
    pass


@dataclass(frozen=True)
class HoldingView:
    instrument: str
    name: str
    units: Decimal
    price: Decimal
    price_as_of: date
    value: Decimal
    cost_basis: Decimal
    pnl: Decimal
    pnl_pct: Decimal


@dataclass
class PortfolioView:
    account_id: str
    as_of: date
    total_value: Decimal = Decimal("0.00")
    total_cost: Decimal = Decimal("0.00")
    pnl: Decimal = Decimal("0.00")
    pnl_pct: Decimal = Decimal("0.00")
    holdings: list[HoldingView] = field(default_factory=list)
    by_fund: dict[str, Decimal] = field(default_factory=dict)
    by_asset_class: dict[str, Decimal] = field(default_factory=dict)
    by_region: dict[str, Decimal] = field(default_factory=dict)


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0.00")
    return q_cash(numerator / denominator * Decimal("100"))


def valuation(db: Session, account_id: str, as_of: date) -> PortfolioView:
    view = PortfolioView(account_id=account_id, as_of=as_of)
    by_class: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    by_region: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for h in holdings(db, account_id):
        fund = db.scalar(select(Fund).where(Fund.code == h.instrument))
        price = latest_price(db, h.instrument, as_of) if fund is not None else None
        if fund is None or price is None:
            raise PriceUnavailable(f"no published price for {h.instrument} on or before {as_of}")
        value = q_cash(h.units * price.nav)
        pnl = q_cash(value - h.cost_basis)
        view.holdings.append(HoldingView(
            instrument=h.instrument, name=fund.name, units=h.units, price=price.nav, price_as_of=price.as_of,
            value=value, cost_basis=h.cost_basis, pnl=pnl, pnl_pct=_pct(pnl, h.cost_basis),
        ))
        view.by_fund[h.instrument] = value
        for c in fund.constituents:
            slice_value = value * c.weight
            by_class[c.asset_class] += slice_value
            by_region[c.region] += slice_value
        view.total_value += value
        view.total_cost += h.cost_basis

    view.total_value = q_cash(view.total_value)
    view.total_cost = q_cash(view.total_cost)
    view.pnl = q_cash(view.total_value - view.total_cost)
    view.pnl_pct = _pct(view.pnl, view.total_cost)
    view.by_asset_class = {k: q_cash(v) for k, v in sorted(by_class.items())}
    view.by_region = {k: q_cash(v) for k, v in sorted(by_region.items())}
    return view
