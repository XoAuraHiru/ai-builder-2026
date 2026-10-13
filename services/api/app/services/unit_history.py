"""A house fund's unit price over the long run (front-door analyzer): published daily prices from launch, and before
launch the monthly backtest of the fund's ETF mix, chained backward from the first published price so the two join
without a jump. Monthly history rows are month-end closes labelled with the month's first day, so each backtest
point is dated at its month's end. Backtest points are flagged: the fund did not exist then."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd

from app.models import Fund
from app.services.fund_returns import constituent_weights, fund_returns

BASE = 100.0


def unit_history(fund: Fund, published: list[tuple[date, Decimal]], returns: pd.DataFrame | None = None) -> list[dict]:
    r = fund_returns(constituent_weights(fund), returns)
    month_ends = [(ts + pd.offsets.MonthEnd(0)).date() for ts in r.index]
    growth = list(r.to_numpy())
    launch = published[0][0] if published else None
    # Month ends before launch, and one more point a month earlier than the first return (the series' start level).
    keep = [i for i, d in enumerate(month_ends) if launch is None or d < launch]
    points: list[dict] = []
    if keep:
        last = keep[-1]
        level = float(published[0][1]) if published else BASE * float((1 + r.iloc[: last + 1]).prod())
        levels = {last: level}
        for i in range(last, 0, -1):
            levels[i - 1] = levels[i] / (1 + growth[i])
        start = (r.index[0] - pd.offsets.MonthEnd(1)).date()
        points.append({"date": start, "price": round(levels[0] / (1 + growth[0]), 4), "backtest": True})
        points += [{"date": month_ends[i], "price": round(levels[i], 4), "backtest": True} for i in range(last + 1)]
    points += [{"date": d, "price": round(float(nav), 4), "backtest": False} for d, nav in published]
    return points
