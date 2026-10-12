"""Lifecycle Trust Score, stage 4: trading (blueprint section 6.4).

An account starts from the score its lead earned at conversion (or 100) and fixed rule weights move it, so the same
activity always gives the same score. The response is proportional: a review band adds friction (the investor confirms),
a high-risk band or a possible takeover holds the order for an advisor. Nothing here blocks on its own.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.services.trust import TrustReport, TrustSignal

NEW_DEVICE = timedelta(hours=24)
DORMANT = timedelta(days=90)
RAPID_WINDOW = timedelta(minutes=10)
RAPID_ORDERS = 3
TAKEOVER_SHARE_OF_TRADED = Decimal("0.5")    # of the shares and ETFs held directly...
TAKEOVER_MATERIAL = Decimal("0.10")          # ...when that is also at least this share of the account
TAKEOVER_SHARE_OF_ACCOUNT = Decimal("0.25")  # or this share of the whole account on its own


@dataclass(frozen=True)
class TrustInputs:
    baseline: int
    baseline_source: str
    device_sent: bool
    device_first_seen: datetime | None  # None: never seen on this account (or no device sent)
    last_activity: datetime | None      # the last order or instruction before this one
    recent_orders: int                  # orders placed in the last ten minutes
    now: datetime


def ago(delta: timedelta) -> str:
    hours = int(delta.total_seconds() // 3600)
    if hours < 1:
        return "less than an hour ago"
    if hours < 48:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    return f"{delta.days} days ago"


def assess_account(t: TrustInputs, *, side: str, order_value: Decimal, traded_value: Decimal,
                   account_value: Decimal) -> tuple[TrustReport, bool]:
    signals: list[TrustSignal] = []
    new_device = t.device_first_seen is None or t.now - t.device_first_seen < NEW_DEVICE
    if not t.device_sent:
        signals.append(TrustSignal("T20", "Unrecognised device", -10, "The request carried no device identifier.",
                                   "rule"))
    elif new_device:
        evidence = ("First use of this device on this account." if t.device_first_seen is None
                    else f"This device was first seen {ago(t.now - t.device_first_seen)}.")
        signals.append(TrustSignal("T20", "New device", -10, evidence, "rule"))
    if t.last_activity is not None and t.now - t.last_activity > DORMANT:
        signals.append(TrustSignal("T21", "Dormant account reactivated", -15,
                                   f"No orders or instructions for {(t.now - t.last_activity).days} days.", "rule"))
    if t.recent_orders >= RAPID_ORDERS:
        signals.append(TrustSignal("T22", "Rapid ordering", -10, f"{t.recent_orders} orders in the last ten minutes.",
                                   "rule"))
    takeover = False
    if side == "sell" and new_device:
        of_traded = order_value / traded_value if traded_value > 0 else Decimal("0")
        of_account = order_value / account_value if account_value > 0 else Decimal("0")
        if (of_traded >= TAKEOVER_SHARE_OF_TRADED and of_account >= TAKEOVER_MATERIAL) \
                or of_account >= TAKEOVER_SHARE_OF_ACCOUNT:
            takeover = True
            signals.append(TrustSignal(
                "T23", "Large sale from a new device", -40,
                f"Selling {float(of_traded):.0%} of the shares and ETFs held directly, from a device first seen "
                "within a day.", "rule"))
    score = max(0, min(100, t.baseline + sum(s.weight for s in signals)))
    band = "clear" if score >= 80 else "review" if score >= 50 else "high_risk"
    return TrustReport(score=score, band=band, signals=signals), takeover
