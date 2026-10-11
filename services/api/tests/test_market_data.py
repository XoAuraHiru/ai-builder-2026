import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from app.config import Settings
from app.services.market_data import FakeMarketData, MarketDataError, YFinanceMarketData, get_market_data


def test_fake_history_is_business_days_and_deterministic():
    md = FakeMarketData(seed=7)
    df = md.history(["VTI", "BND"], date(2026, 1, 1), date(2026, 1, 31))
    assert list(df.columns) == ["VTI", "BND"]
    assert len(df) == 22  # business days in Jan 2026
    assert df.index[0] == pd.Timestamp("2026-01-01") and df.index[-1] == pd.Timestamp("2026-01-30")
    assert (df > 0).all().all()
    again = FakeMarketData(seed=7).history(["VTI", "BND"], date(2026, 1, 1), date(2026, 1, 31))
    pd.testing.assert_frame_equal(df, again)
    assert not df["VTI"].equals(df["BND"])  # different tickers, different paths


def test_fake_latest_price_matches_last_history_point():
    md = FakeMarketData(seed=7)
    last = md.history(["VOO"], date(2026, 1, 1), date(2026, 1, 31))["VOO"].iloc[-1]
    assert md.latest_price("VOO", as_of=date(2026, 1, 31)) == Decimal(str(round(float(last), 4)))


def test_fake_rejects_unknown_ticker_pattern():
    with pytest.raises(MarketDataError):
        FakeMarketData().history(["not a ticker"], date(2026, 1, 1), date(2026, 1, 10))


def test_yfinance_empty_frame_raises(tmp_path, monkeypatch):
    import app.services.market_data as mod

    monkeypatch.setattr(mod.yf, "download", lambda *a, **k: pd.DataFrame())
    with pytest.raises(MarketDataError):
        YFinanceMarketData(tmp_path).history(["ZZZZZZ"], date(2026, 1, 1), date(2026, 1, 10))


def test_get_market_data_honours_provider_setting(tmp_path):
    assert isinstance(get_market_data(Settings(_env_file=None, market_data_provider="fake")), FakeMarketData)
    yf_settings = Settings(_env_file=None, market_data_provider="yfinance", market_cache_dir=str(tmp_path))
    assert isinstance(get_market_data(yf_settings), YFinanceMarketData)
    with pytest.raises(MarketDataError):
        get_market_data(Settings(_env_file=None, market_data_provider="bloomberg"))


@pytest.mark.network
@pytest.mark.skipif(os.environ.get("ATRIUM_NETWORK_TESTS") != "1", reason="set ATRIUM_NETWORK_TESTS=1 to hit yfinance")
def test_yfinance_real_download(tmp_path):
    df = YFinanceMarketData(Path(tmp_path)).history(["VTI", "BND"], date(2026, 9, 1), date(2026, 9, 30))
    assert {"VTI", "BND"} <= set(df.columns) and len(df) >= 18
