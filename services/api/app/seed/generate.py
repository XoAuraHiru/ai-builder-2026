"""Deterministic synthetic world: 12 people, 9 investor accounts, two years of monthly investing.

Run:  uv run python -m app.seed.generate --seed 42 --provider yfinance
"""
from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Account, Instruction, Person
from app.seed.funds import HOUSE_FUNDS, all_tickers, seed_funds
from app.services.ledger import apply_posting, holdings, q_cash, q_units
from app.services.market_data import get_market_data
from app.services.pricing import build_nav_series, latest_price, publish_prices

# Investors carry a risk band, a monthly contribution and target fund weights. Staff carry none.
PERSONAS: list[dict] = [
    dict(kind="investor", full_name="Priya Raman", email="priya@atrium.demo", country="US", risk_band=3,
         monthly="1500", funds={"ATR-BAL": 0.6, "ATR-GRW": 0.4}),
    dict(kind="advisor", full_name="Daniel Okafor", email="daniel@atrium.demo", country="US"),
    dict(kind="ops", full_name="Mei Tanaka", email="mei@atrium.demo", country="SG"),
    dict(kind="investor", full_name="Lucas Moreau", email="lucas@atrium.demo", country="US", risk_band=4,
         monthly="2500", funds={"ATR-GRW": 0.5, "ATR-TEC": 0.3, "ATR-GLB": 0.2}),
    dict(kind="investor", full_name="Aisha Khan", email="aisha@atrium.demo", country="US", risk_band=2,
         monthly="800", funds={"ATR-INC": 0.7, "ATR-CASH": 0.3}),
    dict(kind="investor", full_name="Tom Becker", email="tom@atrium.demo", country="US", risk_band=5,
         monthly="3000", funds={"ATR-TEC": 0.6, "ATR-GRW": 0.4}),
    dict(kind="investor", full_name="Sofia Rossi", email="sofia@atrium.demo", country="US", risk_band=3,
         monthly="1200", funds={"ATR-DIV": 0.5, "ATR-BAL": 0.5}),
    dict(kind="investor", full_name="Noah Williams", email="noah@atrium.demo", country="US", risk_band=1,
         monthly="500", funds={"ATR-CASH": 1.0}),
    dict(kind="investor", full_name="Hana Sato", email="hana@atrium.demo", country="JP", risk_band=4,
         monthly="2000", funds={"ATR-GLB": 0.6, "ATR-GRW": 0.4}),
    dict(kind="investor", full_name="Arjun Mehta", email="arjun@atrium.demo", country="US", risk_band=3,
         monthly="1000", funds={"ATR-BAL": 1.0}),
    dict(kind="investor", full_name="Grace Li", email="grace@atrium.demo", country="US", risk_band=2,
         monthly="700", funds={"ATR-INC": 0.5, "ATR-DIV": 0.5}),
    dict(kind="compliance", full_name="Omar Haddad", email="omar@atrium.demo", country="US"),
]


@dataclass
class GenerateReport:
    people: int
    accounts: int
    instructions: int
    postings: int
    prices: int
    last_price_date: date


def is_seeded(db: Session) -> bool:
    return (db.scalar(select(func.count()).select_from(Person)) or 0) > 0


def _month_starts(start: date, end: date) -> list[date]:
    out: list[date] = []
    d = date(start.year, start.month, 1)
    while d <= end:
        out.append(d)
        d = date(d.year + (d.month // 12), (d.month % 12) + 1, 1)
    return out


def _trading_day_on_or_after(d: date, trading_days: set[date]) -> date | None:
    for i in range(7):
        candidate = d + timedelta(days=i)
        if candidate in trading_days:
            return candidate
    return None


def _at(day: date, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)


def generate(db: Session, settings: Settings, *, start: date = date(2024, 10, 1), end: date | None = None) -> GenerateReport:
    end = end or date.today()
    rng = random.Random(settings.seed)
    market = get_market_data(settings)

    # 1. Funds and their daily NAVs from constituent price history.
    seed_funds(db)
    history = market.history(all_tickers(), start, end)
    prices_written = 0
    trading_days: set[date] = set()
    for spec in HOUSE_FUNDS:
        weights = {t: float(w) for (t, w, *_rest) in spec["constituents"]}
        nav = build_nav_series(history, weights)
        prices_written += publish_prices(db, spec["code"], nav, Decimal("1000000"))
        trading_days |= {ts.date() for ts in nav.index}
    db.flush()
    last_price_date = max(trading_days)

    # 2. People, and an account for each investor.
    accounts: list[tuple[Account, dict]] = []
    for i, spec in enumerate(PERSONAS, start=1):
        person = Person(kind=spec["kind"], full_name=spec["full_name"], email=spec["email"],
                        country=spec["country"], risk_band=spec.get("risk_band"))
        db.add(person)
        db.flush()
        if spec["kind"] == "investor":
            acc = Account(person_id=person.id, number=f"ACC-{i:04d}", opened_on=start,
                          bank_last4=f"{rng.randint(1000, 9999)}", bank_verified=True)
            db.add(acc)
            db.flush()
            accounts.append((acc, spec))

    # 3. Monthly subscriptions at that day's NAV; one month in eight, redeem a quarter of the largest holding.
    n_instr = 0
    for acc, spec in accounts:
        monthly = Decimal(spec["monthly"])
        for month in _month_starts(start, end):
            day = _trading_day_on_or_after(month + timedelta(days=rng.randint(0, 5)), trading_days)
            if day is None or day > last_price_date:
                continue
            for code, weight in spec["funds"].items():
                amount = q_cash(monthly * Decimal(str(weight)))
                price = latest_price(db, code, day)
                if price is None:
                    continue
                units = q_units(amount / price.nav)
                instr = Instruction(account_id=acc.id, fund_code=code, type="subscribe", amount=amount,
                                    state="settled", dealing_date=day, requested_at=_at(day, 9), settled_at=_at(day, 18))
                db.add(instr)
                db.flush()
                apply_posting(db, account_id=acc.id, instrument=code, instrument_type="fund",
                              posting_type="subscription", units=units, cash=-amount, price=price.nav,
                              value_date=day, reference=instr.id)
                n_instr += 1
            if rng.random() < 0.125:
                largest = sorted(holdings(db, acc.id), key=lambda h: h.units, reverse=True)
                if largest:
                    h = largest[0]
                    units_out = q_units(h.units * Decimal("0.25"))
                    price = latest_price(db, h.instrument, day)
                    if units_out > 0 and price is not None:
                        cash_in = q_cash(units_out * price.nav)
                        instr = Instruction(account_id=acc.id, fund_code=h.instrument, type="redeem", units=units_out,
                                            state="settled", dealing_date=day, requested_at=_at(day, 10),
                                            settled_at=_at(day, 18))
                        db.add(instr)
                        db.flush()
                        apply_posting(db, account_id=acc.id, instrument=h.instrument, instrument_type="fund",
                                      posting_type="redemption", units=-units_out, cash=cash_in, price=price.nav,
                                      value_date=day, reference=instr.id)
                        n_instr += 1
    db.flush()
    return GenerateReport(people=len(PERSONAS), accounts=len(accounts), instructions=n_instr, postings=n_instr,
                          prices=prices_written, last_price_date=last_price_date)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Atrium synthetic data")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--provider", choices=["fake", "yfinance"], default=None)
    parser.add_argument("--end", type=date.fromisoformat, default=None)
    args = parser.parse_args()
    settings = get_settings()
    if args.seed is not None:
        settings = settings.model_copy(update={"seed": args.seed})
    if args.provider is not None:
        settings = settings.model_copy(update={"market_data_provider": args.provider})

    from app.db import SessionLocal, init_db

    init_db()
    with SessionLocal() as db:
        if is_seeded(db):
            print("database already seeded; nothing to do")
            return
        report = generate(db, settings, end=args.end)
        db.commit()
        print(report)


if __name__ == "__main__":
    main()
