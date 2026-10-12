"""Refresh the committed market files from Yahoo Finance: profiles, daily closes since October 2024 and monthly closes
for the stocks since June 2007 (the ETFs' monthly history is in app/seed/history_monthly.csv).

Run about once a month:  uv run python -m app.markets.refresh
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd

from app.markets.universe import DAILY_PATH, DAILY_START, ETFS, MONTHLY_PATH, PROFILES_PATH, SECTOR_KEYS, STOCKS
from app.seed.history import HISTORY_START


def first_sentence(text: str, limit: int = 240) -> str:
    sentence = (text or "").strip().split(". ")[0].rstrip(".")
    if not sentence:
        return ""
    if len(sentence) > limit - 1:
        return sentence[: limit - 1].rstrip() + "…"
    return sentence + "."


def fetch_profiles() -> dict:
    import yfinance as yf

    out: dict = {}
    for symbol in (*STOCKS, *ETFS):
        info = yf.Ticker(symbol).info
        out[symbol] = {"name": info.get("longName") or info.get("shortName") or symbol,
                       "sector": SECTOR_KEYS.get(info.get("sector") or ""), "industry": info.get("industry"),
                       "category": info.get("category"), "market_cap": info.get("marketCap"),
                       "total_assets": info.get("totalAssets"), "avg_volume": info.get("averageVolume"),
                       "summary": first_sentence(info.get("longBusinessSummary") or "")}
    return out


def fetch_closes(symbols: list[str], start: date, end: date, interval: str) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(symbols, start=start.isoformat(), end=end.isoformat(), interval=interval, auto_adjust=True,
                      progress=False, group_by="column", threads=False)
    close = raw["Close"][symbols].astype("float64")
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.round(4)


def main() -> None:
    today = date.today()
    profiles = fetch_profiles()
    document = {"as_of": today.isoformat(), "source": "Yahoo Finance via yfinance", "symbols": profiles}
    PROFILES_PATH.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    daily = fetch_closes([*STOCKS, *ETFS], DAILY_START, today + timedelta(days=1), "1d").dropna(how="all")
    daily.index.name = "date"
    daily.to_csv(DAILY_PATH, date_format="%Y-%m-%d", lineterminator="\n")
    monthly = fetch_closes(list(STOCKS), HISTORY_START, date(today.year, today.month, 1), "1mo")
    monthly.index.name = "month"
    monthly.to_csv(MONTHLY_PATH, date_format="%Y-%m-%d", lineterminator="\n")
    print(f"profiles for {len(profiles)} symbols; daily {daily.index[0]:%Y-%m-%d} to {daily.index[-1]:%Y-%m-%d}; "
          f"monthly {monthly.index[0]:%Y-%m} to {monthly.index[-1]:%Y-%m}")


if __name__ == "__main__":
    main()
