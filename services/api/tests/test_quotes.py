import threading
import time
from datetime import date, datetime, timezone
from decimal import Decimal

import pandas as pd

from app.markets.quotes import CommittedQuotes, LiveQuotes, market_session, with_spread

DAILY = pd.DataFrame({"AAPL": [100.0, 102.0, 101.0], "VOO": [500.0, 505.0, 510.0]},
                     index=pd.to_datetime(["2026-10-07", "2026-10-08", "2026-10-09"]))


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


def test_committed_quote_is_the_last_close_against_the_one_before():
    q = CommittedQuotes(DAILY).quote("AAPL")
    assert (q.price, q.previous_close, q.source) == (Decimal("101.0000"), Decimal("102.0000"), "close")
    assert q.change == Decimal("-1.0000") and q.change_pct == -0.98
    assert q.as_of == utc("2026-10-09T20:00:00")  # 4 pm in New York, daylight saving time
    assert CommittedQuotes(DAILY).quote("MSFT") is None


def test_close_on_a_past_day_uses_the_close_on_or_before_it():
    book = CommittedQuotes(DAILY)
    assert book.close_on("VOO", date(2026, 10, 8)).price == Decimal("505.0000")
    assert book.close_on("VOO", date(2026, 10, 10)).price == Decimal("510.0000")  # a Saturday
    assert book.close_on("VOO", date(2026, 10, 7)).previous_close == Decimal("500.0000")  # the first close
    assert book.close_on("VOO", date(2026, 10, 1)) is None
    assert list(book.closes("VOO")) == [500.0, 505.0, 510.0]


def test_live_quotes_come_from_one_cached_download():
    calls: list[str] = []
    live = pd.DataFrame({"AAPL": [101.0, 104.5], "VOO": [510.0, 512.0]},
                        index=pd.to_datetime(["2026-10-09", "2026-10-12"]))

    def fetch(symbols, period):
        calls.append(period)
        return live

    t = [0.0]
    book = LiveQuotes(fetch=fetch, ttl=60, clock=lambda: t[0], now=lambda: utc("2026-10-12T15:00:00"), daily=DAILY,
                      background=False)
    q = book.quote("AAPL")
    assert (q.price, q.previous_close, q.source) == (Decimal("104.5000"), Decimal("101.0000"), "live")
    assert q.as_of == utc("2026-10-12T15:00:00")
    book.quote("VOO")
    t[0] = 59.0
    book.quote("AAPL")
    assert calls == ["5d"]
    t[0] = 61.0
    book.quote("AAPL")
    assert calls == ["5d", "5d"]


def test_an_expired_quote_is_served_at_once_while_a_fresh_one_loads():
    first = pd.DataFrame({"KO": [60.0, 61.0]}, index=pd.to_datetime(["2026-10-08", "2026-10-09"]))
    second = pd.DataFrame({"KO": [61.0, 62.0]}, index=pd.to_datetime(["2026-10-09", "2026-10-12"]))
    frames, release = [first, second], threading.Event()

    def fetch(symbols, period):
        if len(frames) == 1:
            release.wait(5)
        return frames.pop(0)

    t = [0.0]
    book = LiveQuotes(fetch=fetch, ttl=60, clock=lambda: t[0], daily=DAILY, background=True)
    assert book.quote("KO").price == Decimal("61.0000")  # the very first load is waited for
    t[0] = 61.0
    started = time.monotonic()
    assert book.quote("KO").price == Decimal("61.0000")  # stale, but answered at once
    assert time.monotonic() - started < 1
    release.set()
    for _ in range(200):
        if book.quote("KO").price == Decimal("62.0000"):
            break
        time.sleep(0.01)
    assert book.quote("KO").price == Decimal("62.0000")


def test_live_quotes_fall_back_to_the_committed_close_and_back_off():
    calls: list[str] = []

    def fetch(symbols, period):
        calls.append(period)
        raise RuntimeError("429 Too Many Requests")

    book = LiveQuotes(fetch=fetch, ttl=60, clock=lambda: 0.0, daily=DAILY)
    q = book.quote("AAPL")
    assert q.source == "close" and q.price == Decimal("101.0000")
    book.quote("VOO")
    assert calls == ["5d"]  # no second attempt inside the minute


def test_live_history_falls_back_to_committed_closes():
    def fetch(symbols, period):
        raise RuntimeError("offline")

    assert list(LiveQuotes(fetch=fetch, daily=DAILY).history("VOO")) == [500.0, 505.0, 510.0]


def test_market_session_follows_new_york_hours_and_holidays():
    assert market_session(utc("2026-10-12T14:00:00")).is_open  # Monday, 10:00 in New York
    before = market_session(utc("2026-10-12T12:00:00"))
    assert not before.is_open and before.label == "Closed. Opens today at 9:30 am New York time."
    friday = market_session(utc("2026-10-09T21:00:00"))
    assert friday.label == "Closed. Opens Monday, October 12 at 9:30 am New York time."
    assert friday.next_open == utc("2026-10-12T13:30:00")
    thanksgiving = market_session(utc("2026-11-26T16:00:00"))
    assert not thanksgiving.is_open and thanksgiving.opens == "tomorrow at 9:30 am New York time"
    assert market_session(utc("2026-10-12T14:00:00")).label == "Open until 4:00 pm New York time."


def test_a_market_order_expects_half_the_spread():
    assert with_spread("buy", "stock", Decimal("100")) == Decimal("100.0200")
    assert with_spread("sell", "etf", Decimal("100")) == Decimal("99.9900")


def test_a_live_frame_past_its_age_limit_is_not_passed_off_as_live():
    live = pd.DataFrame({"AAPL": [101.0, 104.5]}, index=pd.to_datetime(["2026-10-09", "2026-10-12"]))
    frames = [live]

    def fetch(symbols, period):
        if frames:
            return frames.pop(0)
        raise RuntimeError("Yahoo is down")

    t = [0.0]
    book = LiveQuotes(fetch=fetch, ttl=60, max_age=900, clock=lambda: t[0], daily=DAILY, background=False)
    assert book.quote("AAPL").source == "live"
    t[0] = 600.0
    assert book.quote("AAPL").source == "live"  # the refresh failed, but ten minutes old is still a fair quote
    t[0] = 901.0
    q = book.quote("AAPL")
    assert (q.source, q.price) == ("close", Decimal("101.0000"))


def test_the_universe_downloads_in_parallel(monkeypatch):
    import yfinance

    from app.markets.quotes import yahoo_closes

    seen = {}

    def download(symbols, **kwargs):
        seen.update(kwargs)
        frame = pd.DataFrame({("Close", "AAPL"): [100.0, 101.0], ("Close", "KO"): [60.0, 61.0]},
                             index=pd.to_datetime(["2026-10-08", "2026-10-09"]))
        frame.columns = pd.MultiIndex.from_tuples(frame.columns)
        return frame

    monkeypatch.setattr(yfinance, "download", download)
    closes = yahoo_closes(["AAPL", "KO"], "5d")
    assert seen["threads"] is True and seen["period"] == "5d"
    assert list(closes["KO"]) == [60.0, 61.0]
