from decimal import Decimal

from app.markets.refresh import first_sentence
from app.markets.universe import (CASH, ETFS, STOCKS, analytics_returns, band_for_volatility, holding_objects,
                                  instrument, instruments, load_market_daily, xray_profiles)


def test_bands_follow_five_year_volatility():
    assert [band_for_volatility(v) for v in (0.5, 6.5, 13.9, 15.7, 24.7)] == [1, 2, 3, 4, 5]
    assert band_for_volatility(3.0) == 1 and band_for_volatility(3.01) == 2


def test_universe_has_every_symbol_with_a_profile_and_a_band():
    universe = instruments()
    assert set(universe) == set(STOCKS) | set(ETFS) and len(universe) == 47
    assert universe["SGOV"].risk_band == 1 and universe["BND"].risk_band == 2
    assert universe["VOO"].risk_band == 4 and universe["TSLA"].risk_band == 5
    nvda = instrument(" nvda ")
    assert nvda.kind == "stock" and nvda.sector == "technology" and nvda.sector_label == "Technology"
    assert nvda.asset_class == "equity" and nvda.region == "US" and nvda.name.startswith("NVIDIA")
    assert nvda.avg_volume > 1_000_000 and nvda.market_value > 1e12
    assert instrument("BND").asset_class == "bond" and instrument("VXUS").region == "DM_ex_US"
    assert instrument("QQQ").kind == "etf" and instrument("QQQ").sector is None
    assert instrument("ZZZZ") is None


def test_daily_closes_cover_two_years_for_every_symbol():
    daily = load_market_daily()
    assert set(daily.columns) == set(STOCKS) | set(ETFS)
    assert str(daily.index[0].date()) == "2024-10-01" and daily.iloc[-1].notna().all()


def test_analytics_returns_add_stocks_and_a_flat_cash_line():
    r = analytics_returns()
    assert {"AAPL", "VOO", "SPY", "BIL", CASH} <= set(r.columns)
    assert (r[CASH] == 0.0).all()
    assert r["META"].first_valid_index().year == 2012  # listed in May 2012


def test_holdings_become_one_line_funds_for_the_engines():
    objects = holding_objects()
    aapl = objects["AAPL"]
    assert aapl.category == "stock" and aapl.fee_bps == 0 and aapl.risk_band == instrument("AAPL").risk_band
    assert [(c.ticker, c.weight, c.asset_class) for c in aapl.constituents] == [("AAPL", Decimal("1"), "equity")]
    assert objects[CASH].category == "cash" and objects[CASH].constituents[0].asset_class == "cash"


def test_stock_profiles_look_through_to_the_company_itself():
    profiles = xray_profiles()
    assert profiles["MSFT"]["top_holdings"] == [{"symbol": "MSFT", "name": instrument("MSFT").name, "weight": 1.0}]
    assert profiles["MSFT"]["sectors"] == {"technology": 1.0}
    assert profiles["QQQ"]["top_holdings"][0]["symbol"]  # ETF profiles pass through unchanged


def test_first_sentence_trims_long_summaries():
    assert first_sentence("Apple designs phones. It also sells services.") == "Apple designs phones."
    assert first_sentence("") == ""
    assert len(first_sentence("word " * 100)) == 240
