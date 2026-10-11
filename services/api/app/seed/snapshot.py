"""Refresh the committed price snapshot from Yahoo Finance.

Run:  uv run python -m app.seed.snapshot            (start 2024-10-01, end today)
"""
import argparse
import tempfile
from datetime import date
from pathlib import Path

from app.seed.funds import all_tickers
from app.services.market_data import SNAPSHOT_PATH, YFinanceMarketData


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh app/seed/prices_snapshot.csv")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2024, 10, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as cache:
        df = YFinanceMarketData(Path(cache)).history(all_tickers(), args.start, args.end)
    df = df.dropna().round(4)
    df.index.name = "date"
    df.to_csv(SNAPSHOT_PATH, date_format="%Y-%m-%d")
    print(f"wrote {len(df)} rows x {len(df.columns)} tickers to {SNAPSHOT_PATH} ({df.index.min().date()}..{df.index.max().date()})")


if __name__ == "__main__":
    main()
