"""Pre-trade Guardian: six golden orders on synthetic paper accounts get their golden verdicts."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.governance import golden
from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, every_case, run_case, suite
from app.markets.quotes import MarketSession, Quote
from app.markets.universe import CASH, holding_objects, instrument
from app.seed.funds import house_fund_objects
from app.services.account_snapshot import AccountSnapshot, Sale
from app.services.account_trust import TrustInputs
from app.services.guardian import OrderRequest, assess
from app.services.portfolio import HoldingView, PortfolioView

NOW = datetime(2026, 10, 12, 15, tzinfo=timezone.utc)
OPEN = MarketSession(True, NOW, "")


def _trust(device: str) -> TrustInputs:
    first_seen = None if device == "new" else NOW - timedelta(days=300)
    return TrustInputs(100, "no earlier score", True, first_seen, NOW - timedelta(days=2), 0, NOW)


def _holding(code: str, value: str, kind: str, units: str = "1") -> HoldingView:
    v, u = Decimal(value), Decimal(units)
    return HoldingView(instrument=code, name=code, units=u, price=v / u, price_as_of=NOW.date(), value=v,
                       cost_basis=v, pnl=Decimal("0"), pnl_pct=Decimal("0"), kind=kind)


def snapshot(spec: dict) -> AccountSnapshot:
    """A paper account from its golden description: cash, holdings, past sales at a loss, and how known the device is."""
    cash = Decimal(spec.get("cash", "0"))
    rows = ([_holding(CASH, str(cash), "cash")] if cash > 0 else []) + [
        _holding(h["code"], h["value"], h["kind"], h.get("units", "1")) for h in spec.get("holdings", [])]
    view = PortfolioView(account_id="golden", as_of=NOW.date(), total_value=sum((h.value for h in rows), Decimal("0")),
                         holdings=rows, by_instrument={h.instrument: h.value for h in rows}, cash=cash)
    return AccountSnapshot(
        account_id="golden", profile_band=spec.get("band"), view=view,
        funds={**holding_objects(), **house_fund_objects()}, cash=cash, reserved_cash=Decimal("0"),
        units={h.instrument: h.units for h in rows if h.kind in ("stock", "etf")}, reserved_units={}, lots={},
        sales=[Sale(s["symbol"], date.fromisoformat(s["day"]), Decimal(s["gain"])) for s in spec.get("sales", [])],
        buys=[], traded_today={}, day_trades=0, trust=_trust(spec.get("device", "familiar")), today=NOW.date())


@suite("pretrade_guardian")
def golden_orders(ctx: EvalContext) -> SuiteResult:
    cases = []
    for c in golden.load("pretrade_guardian/orders")["cases"]:
        def check(c=c):
            o = c["order"]
            price = Decimal(o["price"])
            order = OrderRequest(o["symbol"], o["side"], o.get("order_type", "market"), int(o["qty"]),
                                 Decimal(o["limit"]) if o.get("limit") else None)
            report = assess(snapshot(c["account"]), order, instrument(o["symbol"]),
                            Quote(o["symbol"], price, price, NOW, "live"), OPEN)
            concerns = {ch.code: ch.outcome for ch in report.checks if ch.outcome not in ("pass", "info")}
            return CaseResult(c["id"], "pass" if report.verdict == c["expect"] else "fail", expected=c["expect"],
                              actual={"verdict": report.verdict, "concerns": concerns}, detail=c["why"])
        cases.append(run_case(c["id"], check))
    return every_case("pretrade_guardian", "golden", "free", cases,
                      bar="Every golden order gets its golden verdict")
