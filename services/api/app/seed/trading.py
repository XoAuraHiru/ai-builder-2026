"""Paper-trading demo data, seeded once: paper cash for every investor, a known phone for each account, and the
positions behind the trading stories.

- Lucas holds NVIDIA directly and through his funds: buying more shows the look-through concentration warning.
- Tom holds a large Tesla position: selling it all from a browser Atrium has not seen before is held as a possible
  account takeover.
- Hana sold a stock at a loss less than three weeks ago: buying it back raises the wash-sale warning.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.markets.quotes import CommittedQuotes, Quote
from app.markets.universe import CASH
from app.models import Account, AccountDevice, Person, Posting, TradeOrder
from app.services.devices import device_hash
from app.services.ledger import apply_posting, q_cash

DEFAULT_CASH = "10000"
# Paper cash left in each account once its seeded positions are bought.
PAPER_CASH = {"priya@atrium.demo": "20000", "lucas@atrium.demo": "15000", "aisha@atrium.demo": "10000",
              "tom@atrium.demo": "12000", "sofia@atrium.demo": "15000", "noah@atrium.demo": "5000",
              "hana@atrium.demo": "25000", "arjun@atrium.demo": "10000", "grace@atrium.demo": "8000"}
# (symbol, shares, bought this many days before the seed date)
POSITIONS = {"lucas@atrium.demo": [("NVDA", 40, 400), ("AAPL", 30, 300), ("MSFT", 15, 250)],
             "tom@atrium.demo": [("TSLA", 120, 330), ("AMD", 20, 200)]}
LOSS_STORY_EMAIL = "hana@atrium.demo"
LOSS_CANDIDATES = ("PEP", "NKE", "KO", "DIS", "UNH", "INTC", "CRM", "ORCL", "PG", "JNJ")
LOSS_SHARES = 40


def _at(day: date, hour: int = 15) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)


def _fill(db: Session, account: Account, symbol: str, side: str, quantity: int, quote: Quote, note: str) -> None:
    day = quote.as_of.date()
    gross = q_cash(quote.price * quantity)
    sign = 1 if side == "buy" else -1
    order = TradeOrder(account_id=account.id, symbol=symbol, side=side, order_type="market", quantity=quantity,
                       state="filled", verdict="proceed", guardian={"seeded": True, "checks": []},
                       estimated_value=gross, fill_price=quote.price, filled_at=_at(day), broker="atrium-paper",
                       trust_score=100, trust_band="clear", created_at=_at(day, 14),
                       timeline=[{"state": "placed", "note": note, "at": _at(day, 14).isoformat()},
                                 {"state": "filled", "note": f"Filled in paper trading at ${quote.price:,.2f} a share.",
                                  "at": _at(day).isoformat()}])
    db.add(order)
    db.flush()
    apply_posting(db, account_id=account.id, instrument=symbol, instrument_type="equity", posting_type=side,
                  units=Decimal(sign * quantity), cash=-sign * gross, price=quote.price, value_date=day,
                  reference=order.id)
    apply_posting(db, account_id=account.id, instrument=CASH, instrument_type="cash", posting_type=side,
                  units=-sign * gross, cash=Decimal("0"), price=Decimal("1"), value_date=day, reference=order.id)


def loss_days(closes: pd.Series, today: date) -> tuple[date, date] | None:
    """The highest close 40 to 90 days ago and the lowest 8 to 20 days ago, when the second is lower."""
    early = closes.loc[pd.Timestamp(today - timedelta(days=90)):pd.Timestamp(today - timedelta(days=40))]
    late = closes.loc[pd.Timestamp(today - timedelta(days=20)):pd.Timestamp(today - timedelta(days=8))]
    if early.empty or late.empty or late.min() >= early.max():
        return None
    return early.idxmax().date(), late.idxmin().date()


def _loss_story(db: Session, account: Account, today: date, quotes: CommittedQuotes) -> None:
    for symbol in LOSS_CANDIDATES:
        days = loss_days(quotes.closes(symbol), today)
        if days is None:
            continue
        bought, sold = (quotes.close_on(symbol, d) for d in days)
        _fill(db, account, symbol, "buy", LOSS_SHARES, bought, "Seeded purchase.")
        _fill(db, account, symbol, "sell", LOSS_SHARES, sold, "Seeded sale at a loss.")
        return


def seed_trading(db: Session, today: date | None = None, quotes: CommittedQuotes | None = None) -> bool:
    """Seed paper-trading data once. Returns False when it already exists or there are no investors yet."""
    if db.scalar(select(Posting.id).where(Posting.instrument_type == "cash").limit(1)) is not None:
        return False
    rows = db.execute(select(Account, Person.email).join(Person, Account.person_id == Person.id)
                      .where(Person.kind == "investor").order_by(Account.number)).all()
    if not rows:
        return False
    today = today or date.today()
    quotes = quotes or CommittedQuotes()
    for account, email in rows:
        db.add(AccountDevice(account_id=account.id, device_hash=device_hash(f"seed-device:{email}"),
                             label="Atrium app on iPhone", first_seen=_at(account.opened_on),
                             last_seen=_at(today - timedelta(days=2))))
        priced = [(symbol, shares, quotes.close_on(symbol, today - timedelta(days=days)))
                  for symbol, shares, days in POSITIONS.get(email, [])]
        priced = [(symbol, shares, quote) for symbol, shares, quote in priced if quote is not None]
        cost = sum((q_cash(quote.price * shares) for _, shares, quote in priced), Decimal("0"))
        amount = Decimal(PAPER_CASH.get(email, DEFAULT_CASH)) + cost
        apply_posting(db, account_id=account.id, instrument=CASH, instrument_type="cash", posting_type="deposit",
                      units=amount, cash=amount, price=Decimal("1"), value_date=account.opened_on,
                      reference="PAPER-CASH")
        for symbol, shares, quote in priced:
            _fill(db, account, symbol, "buy", shares, quote, "Seeded position.")
        if email == LOSS_STORY_EMAIL:
            _loss_story(db, account, today, quotes)
    db.flush()
    return True
