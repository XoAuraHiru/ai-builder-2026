"""The Model Risk Office foundation: the inventory, the breakers, the evaluation framework and its runner."""
from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from sqlalchemy import select

from app.governance import inventory
from app.governance.inventory import KINDS, MODELS, TIERS, missing_sources, version, versions

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
