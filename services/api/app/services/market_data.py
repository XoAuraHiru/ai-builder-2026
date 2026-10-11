from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd
import yfinance as yf

from app.config import Settings

TICKER_RE = re.compile(r"^[A-Z]{1,6}$")


class MarketDataError(Exception):
    pass


class MarketData(Protocol):
    def history(self, tickers: Sequence[str], start: date, end: date) -> pd.DataFrame: ...
    def latest_price(self, ticker: str, as_of: date | None = None) -> Decimal: ...


def _validate(tickers: Sequence[str]) -> list[str]:
    bad = [t for t in tickers if not TICKER_RE.match(t)]
    if bad:
        raise MarketDataError(f"invalid ticker(s): {bad}")
    return list(tickers)


def _to_decimal(x: float) -> Decimal:
    return Decimal(str(round(float(x), 4)))


class FakeMarketData:
    """Deterministic geometric random walk per ticker. For tests and offline demos."""

    EPOCH = date(2020, 1, 1)

    def __init__(self, seed: int = 42, start_price: float = 100.0, drift: float = 0.0003, vol: float = 0.01):
        self.seed, self.start_price, self.drift, self.vol = seed, start_price, drift, vol

    def _path(self, ticker: str, n: int) -> np.ndarray:
        h = int(hashlib.sha256(f"{self.seed}:{ticker}".encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(h)
        rets = rng.normal(self.drift, self.vol, size=n)
        rets[0] = 0.0
        return self.start_price * np.cumprod(1.0 + rets)

    def history(self, tickers: Sequence[str], start: date, end: date) -> pd.DataFrame:
        tickers = _validate(tickers)
        # Every path is anchored at a fixed epoch so overlapping requests agree on prices.
        idx = pd.bdate_range(self.EPOCH, end)
        frame = pd.DataFrame({t: self._path(t, len(idx)) for t in tickers}, index=idx)
        return frame.loc[pd.Timestamp(start):pd.Timestamp(end)]

    def latest_price(self, ticker: str, as_of: date | None = None) -> Decimal:
        as_of = as_of or date.today()
        df = self.history([ticker], as_of - timedelta(days=14), as_of)
        return _to_decimal(df[ticker].iloc[-1])


class YFinanceMarketData:
    """Adjusted closes from Yahoo Finance with a CSV cache keyed by (tickers, start, end)."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def history(self, tickers: Sequence[str], start: date, end: date) -> pd.DataFrame:
        tickers = _validate(tickers)
        key = hashlib.sha1(f"{','.join(sorted(tickers))}|{start}|{end}".encode()).hexdigest()[:16]
        cache = self.cache_dir / f"yf-{key}.csv"
        if cache.exists():
            return pd.read_csv(cache, index_col=0, parse_dates=True)[tickers]
        raw = yf.download(tickers, start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
                          auto_adjust=True, progress=False, group_by="column", threads=False)
        if raw is None or raw.empty:
            raise MarketDataError(f"yfinance returned no data for {tickers} {start}..{end}")
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"]
        else:
            close = raw[["Close"]].rename(columns={"Close": tickers[0]})
        missing = [t for t in tickers if t not in close.columns or close[t].dropna().empty]
        if missing:
            raise MarketDataError(f"yfinance has no prices for {missing}")
        close = close[tickers].astype("float64")
        close.index = pd.to_datetime(close.index).tz_localize(None)
        close.to_csv(cache)
        return close

    def latest_price(self, ticker: str, as_of: date | None = None) -> Decimal:
        _validate([ticker])
        if as_of is not None:
            df = self.history([ticker], as_of - timedelta(days=14), as_of)
            return _to_decimal(df[ticker].dropna().iloc[-1])
        price = getattr(yf.Ticker(ticker).fast_info, "last_price", None)
        if not price:
            raise MarketDataError(f"no last price for {ticker}")
        return _to_decimal(price)


class AlpacaMarketData:
    """Latest trade from Alpaca's data API; history delegated (Alpaca's free data feed is IEX-only)."""

    def __init__(self, api_key: str, secret_key: str, history_provider: MarketData):
        from alpaca.data.historical import StockHistoricalDataClient

        self._client = StockHistoricalDataClient(api_key, secret_key)
        self._history = history_provider

    def history(self, tickers: Sequence[str], start: date, end: date) -> pd.DataFrame:
        return self._history.history(tickers, start, end)

    def latest_price(self, ticker: str, as_of: date | None = None) -> Decimal:
        _validate([ticker])
        if as_of is not None:
            return self._history.latest_price(ticker, as_of)
        from alpaca.data.requests import StockLatestTradeRequest

        trades = self._client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=ticker))
        trade = trades.get(ticker)
        if trade is None:
            raise MarketDataError(f"Alpaca has no latest trade for {ticker}")
        return _to_decimal(trade.price)


def get_market_data(settings: Settings) -> MarketData:
    provider = settings.market_data_provider.lower()
    if provider == "fake":
        return FakeMarketData(seed=settings.seed)
    if provider == "yfinance":
        return YFinanceMarketData(Path(settings.market_cache_dir))
    if provider == "alpaca":
        if not settings.alpaca_api_key or not settings.alpaca_secret_key:
            raise MarketDataError("ALPACA_API_KEY and ALPACA_SECRET_KEY are required for provider=alpaca")
        return AlpacaMarketData(settings.alpaca_api_key, settings.alpaca_secret_key,
                                YFinanceMarketData(Path(settings.market_cache_dir)))
    raise MarketDataError(f"unknown market data provider {provider!r}")
