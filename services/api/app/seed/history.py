"""Long monthly price history and ETF look-through profiles for the Invest features, committed to the repo.

The What-if Studio, risk analytics, X-ray and fund documents read these files, so production never depends on Yahoo
being reachable from a cloud IP. Refresh about once a month:  uv run python -m app.seed.history
"""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.seed.funds import all_tickers

HERE = Path(__file__).resolve().parent
HISTORY_PATH = HERE / "history_monthly.csv"
PROFILES_PATH = HERE / "etf_profiles.json"
HISTORY_START = date(2007, 6, 1)
BENCHMARK = "SPY"  # S&P 500, for beta
RISK_FREE = "BIL"  # 1-3 month Treasury bills, for the Sharpe ratio


def history_tickers() -> list[str]:
    return [*all_tickers(), BENCHMARK]


def fetch_history(end: date) -> pd.DataFrame:
    """Month-end adjusted closes from HISTORY_START up to the month before `end` (whole months only)."""
    import yfinance as yf

    tickers = history_tickers()
    raw = yf.download(tickers, start=HISTORY_START.isoformat(), end=end.isoformat(), interval="1mo",
                      auto_adjust=True, progress=False, group_by="column", threads=False)
    close = raw["Close"][tickers].astype("float64")
    close.index = pd.to_datetime(close.index).tz_localize(None)
    close.index.name = "month"
    return close.round(4)


def fetch_profiles() -> dict:
    """Expense ratio for every ETF; top-ten holdings and sector weights for the equity ETFs."""
    import yfinance as yf

    out: dict = {}
    for ticker in history_tickers():
        data = yf.Ticker(ticker).funds_data
        ops = data.fund_operations
        ratio = None
        if ops is not None and not ops.empty and "Annual Report Expense Ratio" in ops.index:
            ratio = round(float(ops.loc["Annual Report Expense Ratio"].iloc[0]), 6)
        holdings = []
        top = data.top_holdings
        if top is not None and len(top) >= 3:  # bond and cash ETFs report none, or a stray single line
            for symbol, row in top.iterrows():
                holdings.append({"symbol": str(symbol), "name": str(row["Name"]),
                                 "weight": round(float(row["Holding Percent"]), 6)})
        sectors = {k: round(float(v), 6) for k, v in (data.sector_weightings or {}).items() if v}
        out[ticker] = {"expense_ratio": ratio, "top_holdings": holdings, "sectors": sectors}
    return out


@lru_cache(maxsize=1)
def load_monthly_history() -> pd.DataFrame:
    return pd.read_csv(HISTORY_PATH, index_col=0, parse_dates=True).sort_index()


@lru_cache(maxsize=1)
def load_etf_document() -> dict:
    return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))


def load_etf_profiles() -> dict:
    return load_etf_document()["etfs"]


def main() -> None:
    today = date.today()
    history = fetch_history(date(today.year, today.month, 1))
    history.to_csv(HISTORY_PATH, lineterminator="\n")
    document = {"as_of": today.isoformat(), "source": "Yahoo Finance via yfinance", "etfs": fetch_profiles()}
    PROFILES_PATH.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"history {history.index[0]:%Y-%m} to {history.index[-1]:%Y-%m} ({len(history)} months); "
          f"profiles for {len(document['etfs'])} ETFs")


if __name__ == "__main__":
    main()
