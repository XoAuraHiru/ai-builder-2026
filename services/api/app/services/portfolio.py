from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.markets.quotes import CommittedQuotes, get_quotes
from app.markets.universe import CASH_NAME, instrument
from app.models import Fund
from app.services.ledger import Holding, holdings, q_cash
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
    kind: str = "fund"            # fund | stock | etf | cash
    risk_band: int | None = None


@dataclass
class PortfolioView:
    account_id: str
    as_of: date
    total_value: Decimal = Decimal("0.00")
    total_cost: Decimal = Decimal("0.00")
    pnl: Decimal = Decimal("0.00")
    pnl_pct: Decimal = Decimal("0.00")
    holdings: list[HoldingView] = field(default_factory=list)
    by_fund: dict[str, Decimal] = field(default_factory=dict)        # house funds only (What-if reads this)
    by_asset_class: dict[str, Decimal] = field(default_factory=dict)
    by_region: dict[str, Decimal] = field(default_factory=dict)
    by_instrument: dict[str, Decimal] = field(default_factory=dict)  # every holding: funds, shares and cash
    cash: Decimal = Decimal("0.00")                                  # paper cash for trading


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0.00")
    return q_cash(numerator / denominator * Decimal("100"))


def _row(h: Holding, name: str, price: Decimal, price_as_of: date, kind: str, band: int | None) -> HoldingView:
    value = q_cash(h.units * price)
    pnl = q_cash(value - h.cost_basis)
    return HoldingView(instrument=h.instrument, name=name, units=h.units, price=price, price_as_of=price_as_of,
                       value=value, cost_basis=h.cost_basis, pnl=pnl, pnl_pct=_pct(pnl, h.cost_basis), kind=kind,
                       risk_band=band)


def valuation(db: Session, account_id: str, as_of: date, quotes: CommittedQuotes | None = None) -> PortfolioView:
    """Funds at their last published price, shares at the quote (or the close on a past date), cash at face value."""
    view = PortfolioView(account_id=account_id, as_of=as_of)
    by_class: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    by_region: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for h in holdings(db, account_id):
        if h.instrument_type == "cash":
            row = _row(h, CASH_NAME, Decimal("1"), as_of, "cash", None)
            slices = [("cash", "US", Decimal("1"))]
            view.cash = row.value
        elif h.instrument_type == "equity":
            inst = instrument(h.instrument)
            quote = (quotes or get_quotes()).price_on(h.instrument, as_of) if inst is not None else None
            if inst is None or quote is None:
                raise PriceUnavailable(f"no price for {h.instrument} on or before {as_of}")
            row = _row(h, inst.name, quote.price, quote.as_of.date(), inst.kind, inst.risk_band)
            slices = [(inst.asset_class, inst.region, Decimal("1"))]
        else:
            fund = db.scalar(select(Fund).where(Fund.code == h.instrument))
            price = latest_price(db, h.instrument, as_of) if fund is not None else None
            if fund is None or price is None:
                raise PriceUnavailable(f"no published price for {h.instrument} on or before {as_of}")
            row = _row(h, fund.name, price.nav, price.as_of, "fund", fund.risk_band)
            slices = [(c.asset_class, c.region, c.weight) for c in fund.constituents]
            view.by_fund[h.instrument] = row.value
        view.holdings.append(row)
        view.by_instrument[h.instrument] = row.value
        for asset_class, region, share in slices:
            by_class[asset_class] += row.value * share
            by_region[region] += row.value * share
        view.total_value += row.value
        view.total_cost += h.cost_basis

    view.total_value = q_cash(view.total_value)
    view.total_cost = q_cash(view.total_cost)
    view.pnl = q_cash(view.total_value - view.total_cost)
    view.pnl_pct = _pct(view.pnl, view.total_cost)
    view.by_asset_class = {k: q_cash(v) for k, v in sorted(by_class.items())}
    view.by_region = {k: q_cash(v) for k, v in sorted(by_region.items())}
    return view
