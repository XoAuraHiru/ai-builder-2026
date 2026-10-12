import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.markets.quotes import MarketSession, Quote
from app.markets.universe import CASH, holding_objects, instrument
from app.seed.funds import house_fund_objects
from app.services.account_snapshot import AccountSnapshot, Sale
from app.services.account_trust import TrustInputs
from app.services.guardian import OrderRequest, assess, report_facts, report_json
from app.services.instructions import LotView
from app.services.portfolio import HoldingView, PortfolioView

NOW = datetime(2026, 10, 12, 15, tzinfo=timezone.utc)
OPEN = MarketSession(True, NOW, "")
CLOSED = MarketSession(False, NOW + timedelta(hours=18), "Tuesday, October 13 at 9:30 am New York time")
FAMILIAR = TrustInputs(100, "no earlier score", True, NOW - timedelta(days=300), NOW - timedelta(days=2), 0, NOW)


def holding(code, value, kind, units="1"):
    v, u = Decimal(value), Decimal(units)
    return HoldingView(instrument=code, name=code, units=u, price=v / u, price_as_of=NOW.date(), value=v,
                       cost_basis=v, pnl=Decimal("0"), pnl_pct=Decimal("0"), kind=kind)


def snap(*, band=4, cash="20000", rows=(), reserved_cash="0", reserved_units=None, sales=(), buys=(),
         traded_today=None, day_trades=0, lots=None, trust=FAMILIAR):
    rows = ([holding(CASH, cash, "cash")] if Decimal(cash) > 0 else []) + list(rows)
    view = PortfolioView(account_id="a1", as_of=NOW.date(), total_value=sum((h.value for h in rows), Decimal("0")),
                         holdings=rows, by_instrument={h.instrument: h.value for h in rows}, cash=Decimal(cash))
    return AccountSnapshot(
        account_id="a1", profile_band=band, view=view, funds={**holding_objects(), **house_fund_objects()},
        cash=Decimal(cash), reserved_cash=Decimal(reserved_cash),
        units={h.instrument: h.units for h in rows if h.kind in ("stock", "etf")}, reserved_units=reserved_units or {},
        lots=lots or {}, sales=list(sales), buys=list(buys), traded_today=traded_today or {}, day_trades=day_trades,
        trust=trust, today=NOW.date())


def run(s, symbol, side="buy", qty=10, price="100", order_type="market", limit=None, session=OPEN):
    quote = Quote(symbol, Decimal(price), Decimal(price), NOW, "live")
    order = OrderRequest(symbol, side, order_type, qty, Decimal(limit) if limit else None)
    return assess(s, order, instrument(symbol), quote, session)


def check(report, code):
    return next(c for c in report.checks if c.code == code)


def test_an_ordinary_buy_proceeds_and_every_check_says_why():
    r = run(snap(), "KO", qty=10, price="60")
    assert r.verdict == "proceed"
    assert [c.code for c in r.checks] == ["PROFILE", "FUNDS", "SUITABILITY", "CONCENTRATION", "SIZE", "LIQUIDITY",
                                          "TIMING", "TRUST"]
    assert all(c.outcome == "pass" for c in r.checks) and all(c.detail for c in r.checks)
    e = r.estimate
    assert (e.price, e.value, e.spread_cost, e.cash_after) == (Decimal("60.0120"), Decimal("600.12"), Decimal("0.12"),
                                                              Decimal("19399.88"))
    assert "3.0% of your account" in check(r, "CONCENTRATION").detail
    assert "$0.12" in check(r, "LIQUIDITY").detail


def test_suitability_warns_one_band_above_and_holds_two_above():
    assert check(run(snap(band=4), "TSLA"), "SUITABILITY").outcome == "warn"
    held = run(snap(band=3), "TSLA")
    assert check(held, "SUITABILITY").outcome == "hold" and held.verdict == "hold"
    assert "2 bands above your profile (band 3)" in check(held, "SUITABILITY").detail
    sell = run(snap(band=1, rows=[holding("TSLA", "4000", "stock", "10")]), "TSLA", side="sell", qty=1, price="400")
    assert check(sell, "SUITABILITY").outcome == "pass"


def test_cash_and_shares_already_promised_cannot_be_spent_again():
    r = run(snap(cash="1000", reserved_cash="600"), "KO", qty=10, price="60")
    assert r.verdict == "block" and check(r, "FUNDS").outcome == "block"
    assert "$400.00 of paper cash free, after $600.00 set aside" in check(r, "FUNDS").detail
    s = snap(rows=[holding("AAPL", "2000", "stock", "10")], reserved_units={"AAPL": Decimal("8")})
    sold = run(s, "AAPL", side="sell", qty=5, price="200")
    assert sold.verdict == "block"
    assert check(sold, "FUNDS").detail == ("You hold 10 shares of AAPL, and 8 are already promised to orders still "
                                           "waiting; this order sells 5.")


def test_lookthrough_concentration_counts_what_funds_hold():
    s = snap(band=5, cash="20000", rows=[holding("ATR-TEC", "20000", "fund")])
    warn = run(s, "NVDA", qty=50, price="200")
    c = check(warn, "CONCENTRATION")
    assert c.outcome == "warn" and "33.19% of your account, up from 8.19%" in c.detail
    assert check(warn, "SECTOR").outcome == "warn" and warn.verdict == "warn"
    held = run(s, "NVDA", qty=70, price="200")
    assert check(held, "CONCENTRATION").outcome == "hold" and held.verdict == "hold"


def test_size_volume_and_far_limits_warn_and_resting_limits_are_explained():
    big = run(snap(band=5, cash="30000000"), "KO", qty=200_000, price="60")
    assert check(big, "SIZE").outcome == "warn" and check(big, "LIQUIDITY").outcome == "warn"
    assert check(run(snap(), "KO", price="100", order_type="limit", limit="110"), "TIMING").outcome == "warn"
    resting = check(run(snap(), "KO", price="100", order_type="limit", limit="95"), "TIMING")
    assert resting.outcome == "info" and "waits until the price falls to it" in resting.detail
    close = run(snap(), "KO", price="100", order_type="limit", limit="101")
    assert check(close, "TIMING").outcome == "pass" and close.estimate.spread_cost == Decimal("0.00")


def test_a_closed_market_is_said_plainly():
    c = check(run(snap(), "KO", price="60", session=CLOSED), "TIMING")
    assert c.outcome == "info" and "closed until Tuesday, October 13" in c.detail and "$60.00" in c.detail


def test_wash_sales_and_day_trading_warn():
    buy_back = run(snap(sales=[Sale("PEP", date(2026, 10, 1), Decimal("-120.50"))]), "PEP", price="125")
    assert check(buy_back, "WASH_SALE").outcome == "warn"
    assert "loss of $120.50 on October 1" in check(buy_back, "WASH_SALE").detail
    s = snap(band=5, cash="5000", rows=[holding("AAPL", "2000", "stock", "10")], buys=[("AAPL", date(2026, 10, 5))],
             lots={"AAPL": [LotView(date(2026, 10, 5), Decimal("10"), Decimal("250"))]},
             traded_today={"AAPL": {"buy"}}, day_trades=3)
    sale = run(s, "AAPL", side="sell", qty=10, price="200")
    assert check(sale, "WASH_SALE").outcome == "warn" and "loss of about $500.40" in check(sale, "WASH_SALE").detail
    assert check(sale, "DAY_TRADING").outcome == "warn" and "day trade number 4" in check(sale, "DAY_TRADING").detail


def test_no_profile_blocks_and_a_possible_takeover_holds():
    r = run(snap(band=None), "KO", price="60")
    assert check(r, "PROFILE").outcome == "block" and r.verdict == "block"
    assert not any(c.code == "SUITABILITY" for c in r.checks)
    new_device = TrustInputs(100, "no earlier score", True, None, NOW - timedelta(days=2), 0, NOW)
    s = snap(band=5, cash="12000", rows=[holding("TSLA", "46000", "stock", "120")], trust=new_device)
    takeover = run(s, "TSLA", side="sell", qty=120, price="383.33")
    assert takeover.takeover and check(takeover, "TRUST").outcome == "hold" and takeover.verdict == "hold"
    assert "Possible account takeover" in check(takeover, "TRUST").detail
    no_device = TrustInputs(100, "no earlier score", False, None, None, 0, NOW)
    assert check(run(snap(trust=no_device), "KO", price="60"), "TRUST").outcome == "info"


def test_the_stored_report_and_the_facts_for_gemini():
    r = run(snap(band=4), "TSLA", qty=3, price="400")
    g = report_json(r)
    json.dumps(g)
    assert g["verdict"] == "warn" and g["order"]["words"].startswith("Buy 3 shares of Tesla")
    assert g["estimate"]["value"] == "1200.24" and g["quote"]["source"] == "live"
    facts = report_facts(g)
    assert facts["estimated_total"] == "$1,200.24" and facts["verdict"] == "warn"
    assert [c["check"] for c in facts["concerns"]] == ["Suitability"]
    assert "Risk profile" in facts["passed_checks"]
