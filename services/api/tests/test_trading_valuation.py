from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from app.markets.quotes import CommittedQuotes
from app.markets.universe import CASH, CASH_NAME, instrument
from app.services.analytics import portfolio_risk, portfolio_xray, universe
from app.services.portfolio import PriceUnavailable, valuation

DAILY = pd.DataFrame({"AAPL": [200.0, 210.0], "KO": [60.0, 61.0]}, index=pd.to_datetime(["2026-10-08", "2026-10-09"]))
HDR = {"X-Dev-User": "priya@example.test"}


@pytest.fixture()
def trader(db, account, paper):
    paper.deposit(account, "10000")
    paper.trade(account, "buy", "AAPL", 10, "190")
    db.commit()
    return account


def test_valuation_prices_shares_at_the_quote_and_cash_at_face_value(db, trader):
    view = valuation(db, trader.id, date.today(), CommittedQuotes(DAILY))
    rows = {h.instrument: h for h in view.holdings}
    aapl, cash = rows["AAPL"], rows[CASH]
    assert (aapl.kind, aapl.price, aapl.value, aapl.pnl) == ("stock", Decimal("210.0000"), Decimal("2100.00"),
                                                            Decimal("200.00"))
    assert aapl.risk_band == 5 and aapl.price_as_of == date(2026, 10, 9)
    assert (cash.kind, cash.name, cash.value, cash.pnl) == ("cash", CASH_NAME, Decimal("8100.00"), Decimal("0.00"))
    assert view.cash == Decimal("8100.00") and view.total_value == Decimal("10200.00")
    assert view.by_fund == {} and view.by_instrument == {"AAPL": Decimal("2100.00"), CASH: Decimal("8100.00")}
    assert view.by_asset_class == {"cash": Decimal("8100.00"), "equity": Decimal("2100.00")}


def test_a_past_valuation_uses_the_close_on_that_day(db, trader):
    view = valuation(db, trader.id, date(2026, 10, 8), CommittedQuotes(DAILY))
    assert next(h for h in view.holdings if h.instrument == "AAPL").value == Decimal("2000.00")


def test_a_share_without_a_price_cannot_be_valued(db, trader):
    with pytest.raises(PriceUnavailable):
        valuation(db, trader.id, date(2026, 10, 1), CommittedQuotes(DAILY))


def test_risk_and_xray_read_shares_and_cash_alongside_funds(db, trader):
    view = valuation(db, trader.id, date.today(), CommittedQuotes(DAILY))
    funds = universe(db)
    risk = portfolio_risk(funds, view)
    assert set(risk.weights) == {"AAPL", CASH} and risk.risk_contributions_pct[CASH] == 0.0
    assert risk.portfolio_band == 5  # trading cash is left out of the band
    x = portfolio_xray(funds, view)
    assert x.companies[0].symbol == "AAPL" and x.companies[0].pct == pytest.approx(20.59, abs=0.01)
    assert x.etfs == []  # shares and cash held directly are not ETFs
    assert {s.name for s in x.sectors} == {"Technology", "Cash and T-bills"}
    assert not any(w.code in ("ONE_FUND", "CONC_FUND") for w in x.warnings)


def test_a_cash_only_account_still_gets_a_risk_report(db, account, paper):
    paper.deposit(account, "5000")
    db.commit()
    view = valuation(db, account.id, date.today(), CommittedQuotes(DAILY))
    risk = portfolio_risk(universe(db), view)
    assert risk.portfolio_band == 1 and risk.annual_volatility_pct == 0.0


def test_portfolio_endpoint_reports_kinds_and_cash(client, trader):
    body = client.get(f"/accounts/{trader.id}/portfolio", headers=HDR).json()
    assert {h["instrument"]: h["kind"] for h in body["holdings"]} == {"AAPL": "stock", CASH: "cash"}
    assert body["by_fund"] == {} and set(body["by_instrument"]) == {"AAPL", CASH}
    assert Decimal(body["cash"]) == Decimal("8100.00")


def test_risk_endpoint_names_every_holding(client, trader):
    r = client.get(f"/accounts/{trader.id}/risk", headers=HDR)
    assert r.status_code == 200, r.text
    assert r.json()["names"] == {"AAPL": instrument("AAPL").name, CASH: CASH_NAME}
