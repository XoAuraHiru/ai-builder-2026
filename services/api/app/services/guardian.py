"""Pre-trade Guardian (C3). Fixed rules check every order before it reaches a broker and return one verdict:

- proceed: nothing in the checks stops the order;
- warn:    the investor confirms the warnings before it is sent;
- hold:    an advisor reviews it before anything is sent;
- block:   it cannot be placed as it stands.

Gemini explains the verdict (C4) but never sets it, so the same order on the same account always gets the same verdict,
and every check says why in a sentence with its figures.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal

from app.markets.quotes import MarketSession, Quote, with_spread
from app.markets.universe import CASH, Instrument, xray_profiles
from app.services.account_snapshot import AccountSnapshot
from app.services.account_trust import assess_account
from app.services.analytics import direct_holdings
from app.services.instructions import InstructionRejected, preview_redemption
from app.services.ledger import InsufficientUnits, q_cash
from app.services.trust import TrustReport
from app.services.xray import xray

RANK = {"pass": 0, "info": 0, "warn": 1, "hold": 2, "block": 3}
VERDICTS = ("proceed", "warn", "hold", "block")
VERDICT_MEANING = {"proceed": "nothing in the checks stops the order",
                   "warn": "the investor confirms the warnings before the order is sent",
                   "hold": "an advisor reviews the order before anything is sent",
                   "block": "the order cannot be placed as it stands"}
COMPANY_WARN_PCT, COMPANY_HOLD_PCT = 15.0, 35.0
SECTOR_WARN_PCT = 40.0
SIZE_WARN_PCT = 25.0
VOLUME_WARN_PCT = 1.0
LIMIT_AWAY_PCT = 5.0
DAY_TRADES_ALLOWED = 3            # a fourth round trip in five trading days is pattern day trading
PDT_MINIMUM = Decimal("25000")
NOT_EQUITY = ("Bonds", "Cash and T-bills")


def usd(x) -> str:
    return f"${Decimal(x):,.2f}"


def shares(x) -> str:
    return format(Decimal(x).normalize(), "f")


def day_words(d: date) -> str:
    return f"{d:%B} {d.day}"


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str                       # buy | sell
    order_type: str                 # market | limit
    quantity: int
    limit_price: Decimal | None = None

    def words(self, name: str) -> str:
        verb = "Buy" if self.side == "buy" else "Sell"
        how = "at market" if self.order_type == "market" else f"with a limit of {usd(self.limit_price)}"
        return f"{verb} {self.quantity} {'share' if self.quantity == 1 else 'shares'} of {name} ({self.symbol}) {how}"


@dataclass(frozen=True)
class Check:
    code: str
    title: str
    outcome: str                    # pass | info | warn | hold | block
    detail: str


@dataclass(frozen=True)
class Estimate:
    quote: Decimal
    price: Decimal                  # expected price a share: quote and half spread, or the limit
    value: Decimal
    spread_cost: Decimal
    cash_after: Decimal             # free paper cash after the order fills
    units_after: Decimal


@dataclass
class GuardianReport:
    order: OrderRequest
    instrument: Instrument
    quote: Quote
    session: MarketSession
    estimate: Estimate
    checks: list[Check]
    trust: TrustReport
    takeover: bool

    @property
    def verdict(self) -> str:
        return VERDICTS[max(RANK[c.outcome] for c in self.checks)]


def assess(snap: AccountSnapshot, order: OrderRequest, inst: Instrument, quote: Quote,
           session: MarketSession) -> GuardianReport:
    if order.order_type == "limit" and order.limit_price is not None:
        price, spread = Decimal(order.limit_price), Decimal("0.00")
    else:
        price = with_spread(order.side, inst.kind, quote.price)
        spread = q_cash(abs(price - quote.price) * order.quantity)
    value = q_cash(price * order.quantity)
    sign = 1 if order.side == "buy" else -1
    held = snap.units.get(order.symbol, Decimal("0"))
    estimate = Estimate(quote=quote.price, price=price, value=value, spread_cost=spread,
                        cash_after=q_cash(snap.cash_free - sign * value), units_after=held + sign * order.quantity)
    trust, takeover = assess_account(snap.trust, side=order.side, order_value=value, traded_value=snap.traded_value,
                                     account_value=snap.view.total_value)
    checks = [_profile(snap), _funds(snap, order, estimate), _suitability(snap, order, inst),
              *_concentration(snap, order, inst, value), _size(snap, value), _liquidity(order, inst, spread),
              _timing(order, inst, quote, session), _wash_sale(snap, order, inst, estimate), _day_trading(snap, order),
              _trust(trust, takeover)]
    return GuardianReport(order=order, instrument=inst, quote=quote, session=session, estimate=estimate,
                          checks=[c for c in checks if c is not None], trust=trust, takeover=takeover)


def _profile(snap: AccountSnapshot) -> Check:
    if snap.profile_band is None:
        return Check("PROFILE", "Risk profile", "block",
                     "Complete your risk profile first: Atrium checks every order against it.")
    return Check("PROFILE", "Risk profile", "pass", f"Your risk profile is band {snap.profile_band}.")


def _funds(snap: AccountSnapshot, order: OrderRequest, est: Estimate) -> Check:
    if order.side == "buy":
        free = snap.cash_free
        aside = (f", after {usd(snap.reserved_cash)} set aside for orders still waiting"
                 if snap.reserved_cash > 0 else "")
        if est.value > free:
            return Check("FUNDS", "Cash available", "block",
                         f"This order needs about {usd(est.value)}; you have {usd(free)} of paper cash free{aside}.")
        return Check("FUNDS", "Cash available", "pass",
                     f"You have {usd(free)} of paper cash free{aside}; about {usd(est.cash_after)} would be left.")
    held, free = snap.units.get(order.symbol, Decimal("0")), snap.units_free(order.symbol)
    if order.quantity > free:
        promised = (f", and {shares(held - free)} are already promised to orders still waiting"
                    if held > free else "")
        return Check("FUNDS", "Shares available", "block",
                     f"You hold {shares(held)} shares of {order.symbol}{promised}; this order sells {order.quantity}.")
    return Check("FUNDS", "Shares available", "pass",
                 f"You hold {shares(held)} shares of {order.symbol}; {shares(est.units_after)} would be left.")


def _suitability(snap: AccountSnapshot, order: OrderRequest, inst: Instrument) -> Check | None:
    band = snap.profile_band
    if band is None:
        return None
    if order.side == "sell":
        return Check("SUITABILITY", "Suitability", "pass", f"Selling reduces your exposure to {inst.name}.")
    gap = inst.risk_band - band
    swings = f"Its price has swung about {inst.volatility_pct}% a year over the last five years."
    if gap <= 0:
        return Check("SUITABILITY", "Suitability", "pass",
                     f"{inst.name} is risk band {inst.risk_band}, within your profile (band {band}).")
    if gap == 1:
        return Check("SUITABILITY", "Suitability", "warn",
                     f"{inst.name} is risk band {inst.risk_band}, one above your profile (band {band}). {swings}")
    return Check("SUITABILITY", "Suitability", "hold",
                 f"{inst.name} is risk band {inst.risk_band}, {gap} bands above your profile (band {band}). {swings} "
                 "An advisor reviews an order this far outside a profile before it is sent.")


def _after(snap: AccountSnapshot, order: OrderRequest, value: Decimal) -> dict[str, float]:
    weights = dict(snap.weights)
    weights[order.symbol] = weights.get(order.symbol, 0.0) + float(value)
    weights[CASH] = weights.get(CASH, 0.0) - float(value)
    return {k: v for k, v in weights.items() if v > 0.005}


def _concentration(snap: AccountSnapshot, order: OrderRequest, inst: Instrument, value: Decimal) -> list[Check]:
    """Look through funds and ETFs to the companies and sectors underneath, before and after the purchase."""
    if order.side == "sell" or inst.asset_class != "equity" or not snap.weights:
        return []
    direct = direct_holdings(snap.view) | ({order.symbol} if inst.kind == "stock" else set())
    profiles = xray_profiles()
    before = xray(snap.weights, snap.funds, profiles, direct=frozenset(direct))
    after = xray(_after(snap, order, value), snap.funds, profiles, direct=frozenset(direct))
    out: list[Check] = []
    if inst.kind == "stock":
        was = next((c.pct for c in before.companies if c.symbol == order.symbol), 0.0)
        now = next((c.pct for c in after.companies if c.symbol == order.symbol), 0.0)
        words = (f"Counting what your funds hold, {inst.name} would be {now}% of your account"
                 + (f", up from {was}%." if was else "."))
        if now > COMPANY_HOLD_PCT:
            out.append(Check("CONCENTRATION", "Concentration", "hold",
                             f"{words} Above {COMPANY_HOLD_PCT:.0f}% in one company, an advisor reviews the order."))
        else:
            out.append(Check("CONCENTRATION", "Concentration", "warn" if now > COMPANY_WARN_PCT else "pass", words))
    was_sector = {s.name: s.pct for s in before.sectors}
    grown = [(s.name, s.pct) for s in after.sectors
             if s.name not in NOT_EQUITY and s.pct > was_sector.get(s.name, 0.0)]
    if grown:
        name, share = max(grown, key=lambda x: x[1])
        if share > SECTOR_WARN_PCT:
            out.append(Check("SECTOR", "Sector weight", "warn",
                             f"{name} would be {share}% of your account, up from {was_sector.get(name, 0.0)}%."))
    return out


def _size(snap: AccountSnapshot, value: Decimal) -> Check:
    total = snap.view.total_value
    share = round(float(value) / float(total) * 100, 1) if total > 0 else 0.0
    if share > SIZE_WARN_PCT:
        return Check("SIZE", "Order size", "warn", f"This order is {share}% of your account's value of {usd(total)}.")
    return Check("SIZE", "Order size", "pass", f"This order is {share}% of your account's value.")


def _liquidity(order: OrderRequest, inst: Instrument, spread: Decimal) -> Check:
    cost = f" The estimated spread cost is {usd(spread)}." if order.order_type == "market" else ""
    if not inst.avg_volume:
        return Check("LIQUIDITY", "Liquidity", "info", f"Atrium has no trading volume for {order.symbol}.{cost}")
    share = order.quantity / inst.avg_volume * 100
    typical = f"{inst.avg_volume / 1e6:.1f} million"
    if share > VOLUME_WARN_PCT:
        return Check("LIQUIDITY", "Liquidity", "warn",
                     f"{order.quantity} shares is {share:.1f}% of the {typical} shares of {order.symbol} traded on a "
                     f"typical day, enough to move the price.{cost}")
    return Check("LIQUIDITY", "Liquidity", "pass",
                 f"Small next to the {typical} shares of {order.symbol} traded on a typical day.{cost}")


def _timing(order: OrderRequest, inst: Instrument, quote: Quote, session: MarketSession) -> Check:
    now_price = usd(quote.price)
    if order.order_type == "market":
        if session.is_open:
            return Check("TIMING", "Price and timing", "pass",
                         f"The market is open, so a market order fills at once at about "
                         f"{usd(with_spread(order.side, inst.kind, quote.price))} a share.")
        return Check("TIMING", "Price and timing", "info",
                     f"The US market is closed until {session.opens}. Atrium's paper broker fills a market order at "
                     f"the last close of {now_price} and says so; a real broker would fill it at the next open, at "
                     "the price then.")
    limit = Decimal(order.limit_price)
    away = round(float((limit - quote.price) / quote.price * 100), 1)
    if order.side == "buy" and away > LIMIT_AWAY_PCT:
        return Check("TIMING", "Price and timing", "warn",
                     f"Your limit of {usd(limit)} is {away}% above the current price of {now_price}: you could pay "
                     "more than you need to.")
    if order.side == "buy" and away < 0:
        return Check("TIMING", "Price and timing", "info",
                     f"Your limit of {usd(limit)} is below the current price of {now_price}, so the order waits until "
                     "the price falls to it.")
    if order.side == "sell" and -away > LIMIT_AWAY_PCT:
        return Check("TIMING", "Price and timing", "warn",
                     f"Your limit of {usd(limit)} is {-away}% below the current price of {now_price}: you could sell "
                     "for less than you need to.")
    if order.side == "sell" and away > 0:
        return Check("TIMING", "Price and timing", "info",
                     f"Your limit of {usd(limit)} is above the current price of {now_price}, so the order waits until "
                     "the price rises to it.")
    return Check("TIMING", "Price and timing", "pass",
                 f"Your limit of {usd(limit)} is close to the current price of {now_price}, so the order should fill "
                 "at once.")


def _wash_sale(snap: AccountSnapshot, order: OrderRequest, inst: Instrument, est: Estimate) -> Check | None:
    if order.side == "buy":
        losses = [s for s in snap.sales if s.symbol == order.symbol and s.gain < 0]
        if not losses:
            return None
        last = max(losses, key=lambda s: s.day)
        return Check("WASH_SALE", "Wash sale", "warn",
                     f"You sold {inst.name} at a loss of {usd(-last.gain)} on {day_words(last.day)}. Buying it back "
                     "within 30 days makes that a wash sale, so the loss cannot be claimed for taxes now. Not tax "
                     "advice.")
    bought = [day for symbol, day in snap.buys if symbol == order.symbol]
    if not bought:
        return None
    try:
        sale = preview_redemption(order.symbol, snap.lots.get(order.symbol, []), est.price, snap.today,
                                  units=Decimal(order.quantity))
    except (InstructionRejected, InsufficientUnits):
        return None
    if sale.realised_gain >= 0:
        return None
    return Check("WASH_SALE", "Wash sale", "warn",
                 f"This sale would realise a loss of about {usd(-sale.realised_gain)}, and you bought {order.symbol} "
                 f"on {day_words(max(bought))}. A loss within 30 days of a purchase can be a wash sale and not count "
                 "for taxes now. Not tax advice.")


def _day_trading(snap: AccountSnapshot, order: OrderRequest) -> Check | None:
    sides = snap.traded_today.get(order.symbol, set())
    completes = "buy" in sides if order.side == "sell" else "sell" in sides
    if not completes or snap.day_trades < DAY_TRADES_ALLOWED or snap.view.total_value >= PDT_MINIMUM:
        return None
    return Check("DAY_TRADING", "Day trading", "warn",
                 f"This would be day trade number {snap.day_trades + 1} in five trading days. Brokers treat four or "
                 f"more as pattern day trading, which needs at least {usd(PDT_MINIMUM)} in the account.")


def _signal_words(trust: TrustReport, skip: tuple[str, ...] = ()) -> str:
    return "; ".join(f"{s.label.lower()} ({s.evidence[:1].lower()}{s.evidence[1:].rstrip('.')})"
                     for s in trust.signals if s.code not in skip)


def _trust(trust: TrustReport, takeover: bool) -> Check:
    found = _signal_words(trust)
    if takeover:
        others = _signal_words(trust, skip=("T23",))
        return Check("TRUST", "Account trust", "hold",
                     "Possible account takeover: a large sale from a device first seen within a day. An advisor "
                     f"confirms with you before it is sent. Trust score {trust.score} of 100"
                     + (f", with {others}." if others else "."))
    if trust.band == "high_risk":
        return Check("TRUST", "Account trust", "hold",
                     f"Trust score {trust.score} of 100: {found}. An advisor reviews the order before it is sent.")
    if trust.band == "review":
        return Check("TRUST", "Account trust", "warn", f"Trust score {trust.score} of 100: {found}.")
    if trust.signals:
        return Check("TRUST", "Account trust", "info", f"Trust score {trust.score} of 100, still clear: {found}.")
    return Check("TRUST", "Account trust", "pass",
                 f"Trust score {trust.score} of 100: nothing unusual about this device or activity.")


def report_json(r: GuardianReport) -> dict:
    """The report as stored on the order and returned by the API."""
    i = r.instrument
    return {
        "verdict": r.verdict,
        "order": {"symbol": r.order.symbol, "side": r.order.side, "order_type": r.order.order_type,
                  "quantity": r.order.quantity,
                  "limit_price": str(r.order.limit_price) if r.order.limit_price is not None else None,
                  "words": r.order.words(i.name)},
        "instrument": {"symbol": i.symbol, "name": i.name, "kind": i.kind, "risk_band": i.risk_band,
                       "sector_label": i.sector_label, "volatility_pct": i.volatility_pct},
        "quote": {"symbol": r.quote.symbol, "price": str(r.quote.price), "previous_close": str(r.quote.previous_close),
                  "change": str(r.quote.change), "change_pct": r.quote.change_pct,
                  "as_of": r.quote.as_of.isoformat(), "source": r.quote.source},
        "session": {"is_open": r.session.is_open, "label": r.session.label,
                    "next_open": r.session.next_open.isoformat()},
        "estimate": {k: str(v) for k, v in asdict(r.estimate).items()},
        "checks": [asdict(c) for c in r.checks],
        "trust": {"score": r.trust.score, "band": r.trust.band, "signals": [s.as_dict() for s in r.trust.signals]},
        "takeover": r.takeover,
    }


def report_facts(g: dict) -> dict:
    """What Gemini may say about a stored report. Money is pre-formatted, so the figure check can vouch for it."""
    q, est, inst = g["quote"], g["estimate"], g["instrument"]
    source = "a delayed live price" if q["source"] == "live" else f"the last close, on {q['as_of'][:10]}"
    return {
        "order": g["order"]["words"], "market": g["session"]["label"],
        "instrument": {"name": inst["name"], "symbol": inst["symbol"], "risk_band": inst["risk_band"],
                       "five_year_volatility": f"{inst['volatility_pct']}%", "sector": inst["sector_label"]},
        "price_now": usd(q["price"]), "price_source": source, "expected_price": usd(est["price"]),
        "estimated_total": usd(est["value"]), "estimated_spread_cost": usd(est["spread_cost"]),
        "paper_cash_after": usd(est["cash_after"]),
        "verdict": g["verdict"], "verdict_means": VERDICT_MEANING[g["verdict"]],
        "concerns": [{"check": c["title"], "outcome": c["outcome"], "detail": c["detail"]}
                     for c in g["checks"] if c["outcome"] != "pass"],
        "passed_checks": [c["title"] for c in g["checks"] if c["outcome"] == "pass"],
        "account_trust": {"score": g["trust"]["score"], "band": g["trust"]["band"],
                          "signals": [f"{s['label']}: {s['evidence']}" for s in g["trust"]["signals"]]},
    }
