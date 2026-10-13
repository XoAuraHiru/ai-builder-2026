"""The Model Risk Office foundation: the inventory, the breakers, the evaluation framework and its runner."""
from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from sqlalchemy import select

from app.governance import inventory
from app.governance.inventory import KINDS, MODELS, TIERS, missing_sources, version, versions
from app.governance.breakers import BreakerError, BreakerOpen, breaker_message, breaker_open, ensure_closed, reset, trip
from app.models import AIDecision, ModelBreaker, Person

PERSONA_EMAILS = {f"{p}@atrium.demo" for p in ("daniel", "priya", "lucas", "tom", "hana", "mei", "sam", "omar")}
NOT_YET_BUILT = {"scenario_mapper", "call_analyst", "ring_narrator"}  # their modules arrive with the feature plans


def test_the_inventory_lists_every_model_once_with_what_governs_it():
    assert len(MODELS) == 18
    for key, spec in MODELS.items():
        assert spec.key == key and spec.kind in KINDS and spec.tier in TIERS, key
        assert spec.owner in PERSONA_EMAILS and spec.purpose and spec.human_gate and spec.limitations, key
        assert spec.sources, key
    high_with_fallback = {k for k, s in MODELS.items() if s.tier == "high" and s.fallback}
    assert {"reconciler_agent", "case_reviewer", "call_analyst", "draft_compliance"} <= high_with_fallback


def test_every_built_model_resolves_its_sources():
    for key, spec in MODELS.items():
        if key not in NOT_YET_BUILT:
            assert missing_sources(spec) == [], key


def test_a_version_is_stable_and_changes_when_its_text_changes(monkeypatch):
    spec = MODELS["case_reviewer"]
    first = version(spec)
    assert len(first) == 10 and version(spec) == first and versions()["case_reviewer"] == first
    real = inventory._source_text
    monkeypatch.setattr(inventory, "_source_text", lambda s: real(s) + " changed")
    assert version(spec) != first


NOW = datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)


@pytest.fixture()
def omar(db):
    person = Person(kind="compliance", full_name="Omar Haddad", email="omar@atrium.demo", totp_secret="MFRGGZDFMZTWQ2LK")
    db.add(person)
    db.commit()
    return person


def test_a_breaker_is_closed_until_tripped_and_says_why_when_open(db):
    assert breaker_open(db, "case_reviewer") is False and breaker_message(db, "case_reviewer") is None
    ensure_closed(db, "case_reviewer")
    trip(db, "case_reviewer", reason="It missed its bar in the live checks.", by="Live checks", now=NOW)
    db.flush()
    assert breaker_open(db, "case_reviewer") is True
    assert breaker_message(db, "case_reviewer") == "Case review is paused: It missed its bar in the live checks. Since Oct 14."
    with pytest.raises(BreakerOpen) as raised:
        ensure_closed(db, "case_reviewer")
    assert raised.value.key == "case_reviewer" and "paused" in str(raised.value)
    trip(db, "case_reviewer", reason="A second reason.", by="Omar Haddad", now=NOW)
    assert db.get(ModelBreaker, "case_reviewer").reason == "It missed its bar in the live checks."  # the first stays


def test_resetting_needs_a_reason_and_the_current_code(db, omar):
    trip(db, "reconciler_agent", reason="Kill switch for the demo.", by="Omar Haddad", now=NOW)
    with pytest.raises(BreakerError, match="code"):
        reset(db, "reconciler_agent", reason="Fixed.", person=omar, code="000000", now=NOW)
    with pytest.raises(BreakerError, match="reason"):
        reset(db, "reconciler_agent", reason="  ", person=omar, code=pyotp.TOTP(omar.totp_secret).at(NOW), now=NOW)
    row = reset(db, "reconciler_agent", reason="The prompt was fixed and revalidated.", person=omar,
                code=pyotp.TOTP(omar.totp_secret).at(NOW), now=NOW)
    assert row.state == "closed" and [h["state"] for h in row.history] == ["open", "closed"]
    assert breaker_open(db, "reconciler_agent") is False
    purposes = set(db.scalars(select(AIDecision.purpose)).all())
    assert {"breaker_open", "breaker_reset"} <= purposes
    with pytest.raises(BreakerError, match="not paused"):
        reset(db, "reconciler_agent", reason="Again.", person=omar, code=pyotp.TOTP(omar.totp_secret).at(NOW), now=NOW)
    with pytest.raises(BreakerError, match="no model"):
        trip(db, "made_up", reason="x", by="y", now=NOW)


def test_an_unreadable_breaker_counts_as_open(db, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(db, "get", broken)
    assert breaker_open(db, "case_reviewer") is True
    assert "cannot be checked" in breaker_message(db, "case_reviewer")
