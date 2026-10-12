"""Quotes and market hours (C1).

Delayed prices for the whole universe come from one batched Yahoo Finance download, cached for a minute. When Yahoo is
unreachable, every quote falls back to the committed last close and says so (source "close"); a failed download is not
retried until the minute is up, so an outage costs one slow request a minute rather than every request.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from datetime import time as clock_time
from decimal import ROUND_HALF_EVEN, Decimal
from zoneinfo import ZoneInfo

import pandas as pd

from app.config import get_settings
from app.markets.universe import ETFS, STOCKS, load_market_daily

log = logging.getLogger(__name__)
NEW_YORK = ZoneInfo("America/New_York")
PRICE_Q = Decimal("0.0001")
OPEN, CLOSE = clock_time(9, 30), clock_time(16, 0)
# NYSE full-day closures. Early closes are ignored: the paper broker does not need them.
HOLIDAYS = frozenset(date.fromisoformat(d) for d in (
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
    "2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18",
    "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24"))
# Half the typical bid-ask spread in basis points: what a market order gives up against the quoted price.
HALF_SPREAD_BPS = {"stock": Decimal("2"), "etf": Decimal("1")}

Fetch = Callable[[list[str], str], pd.DataFrame]  # (symbols, period) -> daily closes, one column per symbol


def to_price(x: float) -> Decimal:
    return Decimal(str(x)).quantize(PRICE_Q, rounding=ROUND_HALF_EVEN)


def with_spread(side: str, kind: str, price: Decimal) -> Decimal:
    """The price a market order should expect: half the spread above the quote to buy, below it to sell."""
    shift = HALF_SPREAD_BPS.get(kind, Decimal("2")) / Decimal("10000")
    factor = 1 + shift if side == "buy" else 1 - shift
    return (Decimal(price) * factor).quantize(PRICE_Q, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: Decimal
    previous_close: Decimal
    as_of: datetime  # UTC: when a live price was read, or 4 pm New York time on the day of a close
    source: str      # live | close

    @property
    def change(self) -> Decimal:
        return self.price - self.previous_close

    @property
    def change_pct(self) -> float:
        return round(float(self.change / self.previous_close * 100), 2) if self.previous_close else 0.0


@dataclass(frozen=True)
class MarketSession:
    is_open: bool
    next_open: datetime  # UTC; the current session's open while the market is open
    opens: str           # "Monday, October 12 at 9:30 am New York time"; empty while open

    @property
    def label(self) -> str:
        return "Open until 4:00 pm New York time." if self.is_open else f"Closed. Opens {self.opens}."


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in HOLIDAYS


def _at(d: date, t: clock_time) -> datetime:
    return datetime.combine(d, t, tzinfo=NEW_YORK).astimezone(timezone.utc)


def market_session(now: datetime) -> MarketSession:
    local = now.astimezone(NEW_YORK)
    today = local.date()
    if is_trading_day(today) and OPEN <= local.time() < CLOSE:
        return MarketSession(True, _at(today, OPEN), "")
    day = today if is_trading_day(today) and local.time() < OPEN else today + timedelta(days=1)
    while not is_trading_day(day):
        day += timedelta(days=1)
    when = ("today" if day == today else "tomorrow" if day == today + timedelta(days=1)
            else f"{day:%A}, {day:%B} {day.day}")
    return MarketSession(False, _at(day, OPEN), f"{when} at 9:30 am New York time")


class CommittedQuotes:
    """Quotes from the committed daily closes: the last close against the close before it."""

    def __init__(self, daily: pd.DataFrame | None = None):
        self._daily = load_market_daily() if daily is None else daily

    @staticmethod
    def _from_frame(frame: pd.DataFrame, symbol: str, source: str, observed: datetime | None = None) -> Quote | None:
        if symbol not in frame.columns:
            return None
        series = frame[symbol].dropna()
        if series.empty:
            return None
        previous = series.iloc[-2] if len(series) > 1 else series.iloc[-1]
        return Quote(symbol, to_price(series.iloc[-1]), to_price(previous),
                     observed or _at(series.index[-1].date(), CLOSE), source)

    def quote(self, symbol: str) -> Quote | None:
        return self._from_frame(self._daily, symbol, "close")

    def quotes(self, symbols) -> dict[str, Quote]:
        return {s: q for s in symbols if (q := self.quote(s)) is not None}

    def close_on(self, symbol: str, day: date) -> Quote | None:
        """The close on or before `day`: past valuations and seeded trades."""
        return self._from_frame(self._daily.loc[: pd.Timestamp(day)], symbol, "close")

    def price_on(self, symbol: str, day: date) -> Quote | None:
        return self.quote(symbol) if day >= date.today() else self.close_on(symbol, day)

    def closes(self, symbol: str) -> pd.Series:
        return self._daily[symbol].dropna() if symbol in self._daily.columns else pd.Series(dtype="float64")

    def history(self, symbol: str) -> pd.Series:
        """About a year of daily closes."""
        series = self.closes(symbol)
        return series.loc[series.index[-1] - pd.Timedelta(days=365):] if len(series) else series


def yahoo_closes(symbols: list[str], period: str) -> pd.DataFrame:
    import yfinance as yf

    # threads=True downloads the symbols in parallel: the whole universe in about a second instead of five.
    raw = yf.download(symbols, period=period, interval="1d", auto_adjust=True, progress=False, group_by="column",
                      threads=True)
    if raw is None or raw.empty:
        raise RuntimeError(f"Yahoo Finance returned no prices for {len(symbols)} symbols over {period}")
    close = raw["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(symbols[0])
    close = close.astype("float64")
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close


class LiveQuotes(CommittedQuotes):
    """Delayed quotes from Yahoo Finance for the whole universe at once, cached for `ttl` seconds, and a year of daily
    closes per symbol cached for `history_ttl` seconds. Falls back to the committed closes whenever Yahoo fails.

    The batched download takes several seconds, so once there is a frame, an expired one is still served at once while
    a fresh one loads in the background (`background=True`); only the very first load is waited for. A frame older than
    `max_age` seconds (Yahoo down for a while) is no longer passed off as live: quotes fall back to the committed close,
    which says so."""

    def __init__(self, fetch: Fetch = yahoo_closes, ttl: float = 60.0, history_ttl: float = 900.0,
                 clock: Callable[[], float] = time.monotonic,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc), daily: pd.DataFrame | None = None,
                 background: bool = True, max_age: float = 900.0):
        super().__init__(daily)
        self._fetch, self._ttl, self._history_ttl, self._clock, self._now = fetch, ttl, history_ttl, clock, now
        self._background, self._max_age = background, max_age
        self._loaded_at: float | None = None
        self._lock = threading.Lock()
        self._frame: pd.DataFrame | None = None
        self._observed: datetime | None = None
        self._checked: float | None = None
        self._loading = False
        self._histories: dict[str, tuple[float, pd.Series]] = {}

    def _load(self) -> None:
        try:
            frame, observed = self._fetch([*STOCKS, *ETFS], "5d"), self._now()
        except Exception as e:  # throttling, network, parsing: keep what we have, else use the committed closes
            log.warning("live quotes unavailable: %s", e)
            frame = observed = None
        with self._lock:
            if frame is not None:
                self._frame, self._observed, self._loaded_at = frame, observed, self._clock()
            self._loading = False

    def _fresh(self, frame: pd.DataFrame | None) -> pd.DataFrame | None:
        if frame is None or self._loaded_at is None or self._clock() - self._loaded_at > self._max_age:
            return None
        return frame

    def _live(self) -> pd.DataFrame | None:
        with self._lock:
            due = self._checked is None or self._clock() - self._checked >= self._ttl
            if not due or self._loading:
                return self._fresh(self._frame)
            self._checked, self._loading = self._clock(), True
            stale = self._frame
        if stale is not None and self._background:
            threading.Thread(target=self._load, daemon=True).start()
            return self._fresh(stale)
        self._load()
        return self._fresh(self._frame)

    def quote(self, symbol: str) -> Quote | None:
        frame = self._live()
        if frame is not None:
            q = self._from_frame(frame, symbol, "live", self._observed)
            if q is not None:
                return q
        return super().quote(symbol)

    def history(self, symbol: str) -> pd.Series:
        now = self._clock()
        with self._lock:
            cached = self._histories.get(symbol)
        if cached is not None and now - cached[0] < self._history_ttl:
            return cached[1]
        try:
            series = self._fetch([symbol], "1y")[symbol].dropna()
            if series.empty:
                raise RuntimeError(f"no history for {symbol}")
        except Exception as e:
            log.warning("live history for %s unavailable: %s", symbol, e)
            series = super().history(symbol)
        with self._lock:
            self._histories[symbol] = (now, series)
        return series


_live: LiveQuotes | None = None


def get_quotes() -> CommittedQuotes:
    """Committed closes for tests and offline runs (provider "fake"); live delayed quotes otherwise."""
    global _live
    if get_settings().market_data_provider == "fake":
        return CommittedQuotes()
    if _live is None:
        _live = LiveQuotes()
    return _live


def quote_book() -> CommittedQuotes:
    """FastAPI dependency; tests override it with a CommittedQuotes over a small frame."""
    return get_quotes()
