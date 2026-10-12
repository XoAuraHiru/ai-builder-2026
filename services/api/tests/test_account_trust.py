from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.services.account_trust import TrustInputs, assess_account

NOW = datetime(2026, 10, 12, 15, tzinfo=timezone.utc)


def inputs(**changes) -> TrustInputs:
    base = dict(baseline=100, baseline_source="no earlier score", device_sent=True,
                device_first_seen=NOW - timedelta(days=200), last_activity=NOW - timedelta(days=3), recent_orders=0,
                now=NOW)
    base.update(changes)
    return TrustInputs(**base)


def assess(i, side="buy", value="100", traded="0", account="5000"):
    return assess_account(i, side=side, order_value=Decimal(value), traded_value=Decimal(traded),
                          account_value=Decimal(account))


def test_a_familiar_device_and_ordinary_activity_stay_clear():
    report, takeover = assess(inputs(), side="sell", value="9000", traded="10000", account="50000")
    assert (report.score, report.band, report.signals, takeover) == (100, "clear", [], False)


def test_a_new_device_costs_ten_points_and_says_when_it_appeared():
    report, _ = assess(inputs(device_first_seen=NOW - timedelta(hours=2)))
    assert (report.score, report.band) == (90, "clear")
    assert [(s.code, s.evidence) for s in report.signals] == [("T20", "This device was first seen 2 hours ago.")]
    first, _ = assess(inputs(device_first_seen=None))
    assert first.signals[0].evidence == "First use of this device on this account."
    missing, _ = assess(inputs(device_sent=False, device_first_seen=None))
    assert missing.signals[0].label == "Unrecognised device"


def test_a_large_sale_from_a_new_device_is_a_possible_takeover():
    report, takeover = assess(inputs(device_first_seen=None), side="sell", value="46000", traded="58000",
                              account="180000")
    assert takeover and [s.code for s in report.signals] == ["T20", "T23"]
    assert (report.score, report.band) == (50, "review")
    assert "79%" in report.signals[1].evidence
    _, small = assess(inputs(device_first_seen=None), side="sell", value="5000", traded="58000", account="180000")
    assert not small
    _, familiar = assess(inputs(), side="sell", value="46000", traded="58000", account="180000")
    assert not familiar


def test_selling_all_of_a_small_position_is_not_a_takeover():
    _, takeover = assess(inputs(device_first_seen=None), side="sell", value="305", traded="305", account="10000")
    assert not takeover  # every share held directly, but 3% of the account
    _, large = assess(inputs(device_first_seen=None), side="sell", value="3000", traded="3000", account="10000")
    assert large


def test_dormancy_rapid_orders_and_the_lead_baseline():
    report, _ = assess(inputs(baseline=70, last_activity=NOW - timedelta(days=120), recent_orders=3))
    assert [s.code for s in report.signals] == ["T21", "T22"]
    assert (report.score, report.band) == (45, "high_risk")
