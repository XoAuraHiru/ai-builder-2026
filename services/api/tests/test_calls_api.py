"""Call intelligence over HTTP: analyse an uploaded or a demo call, list a lead's calls, apply the updates an advisor
ticks, play the demo audio; and the seed that adds Ruth Alvarez."""
import json
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.ai.llm import FakeLLM, LLMError, get_llm
from app.events import InProcessEventBus, set_event_bus
from app.governance.breakers import trip
from app.models import Lead, LeadCall
from app.seed.calls import RUTH_EMAIL, seed_call_stories

STAFF = {"X-Dev-User": "daniel@atrium.demo"}
INVESTOR = {"X-Dev-User": "priya@atrium.demo"}
CALLS = Path(__file__).resolve().parents[1] / "app" / "seed" / "calls"
MP3 = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" * 64


def script_reading(name: str, *, flags=(), updates=()) -> dict:
    """What Gemini would return for a demo call: its script as the transcript, plus the flags and updates given as
    (line index, kind or field, severity or value, quote)."""
    script = json.loads((CALLS / f"{name}.json").read_text(encoding="utf-8"))
    lines = script["lines"]
    role = {k: v["role"] for k, v in script["speakers"].items()}
    return {
        "duration_s": script["duration_s"],
        "transcript": [{"start_s": line["start_s"], "speaker": line["speaker"], "role": role[line["speaker"]],
                        "text": line["text"]} for line in lines],
        "summary": "A first call.", "action_items": ["Send the disclosures."], "facts": [],
        "updates": [{"field": field, "proposed": value, "quote": quote, "start_s": lines[i]["start_s"] + 1}
                    for i, field, value, quote in updates],
        "flags": [{"kind": kind, "severity": severity, "quote": quote, "start_s": lines[i]["start_s"] + 1,
                   "rule": "x", "why": "Because."} for i, kind, severity, quote in flags],
    }


PRESSURE = script_reading("pressure", flags=[
    (9, "promissory", "high", "the growth fund basically guarantees 8% a year"),
    (4, "third_party_direction", "high", "She wants it all in the tech fund, right, Aunt Ruth?"),
    (5, "confusion", "medium", "I don't really understand these funds"),
])
DISCOVERY = script_reading("discovery", updates=[
    (3, "horizon_years", "12", "so that's twelve years from now, not fifteen"),
    (5, "monthly_usd", "2000", "so I can put in two thousand dollars a month"),
    (9, "investable_usd", "175000", "about one hundred and seventy-five thousand dollars"),
])


@pytest.fixture()
def ruth(db, people):
    assert seed_call_stories(db) is True
    db.commit()
    return db.scalar(select(Lead).where(Lead.email == RUTH_EMAIL))


@pytest.fixture()
def emma(make_lead):
    return make_lead(full_name="Emma Walsh", email="emma.walsh@example.com", goals="Retire by 55",
                     horizon_years=15, investable_usd=150000, monthly_usd=1500)


def answer(client, reading: dict | None = None, error: Exception | None = None) -> FakeLLM:
    def respond(prompt: str) -> dict:
        if error:
            raise error
        return reading

    llm = FakeLLM({"call_analysis": respond})
    client.app.dependency_overrides[get_llm] = lambda: llm
    return llm


def test_ruth_is_seeded_once_as_a_new_lead_of_daniels(db, people):
    assert seed_call_stories(db) is True
    db.flush()
    assert seed_call_stories(db) is False
    ruth = db.scalar(select(Lead).where(Lead.email == RUTH_EMAIL))
    assert ruth.full_name == "Ruth Alvarez" and ruth.stage == "new" and ruth.owner_id == people["advisor"].id
    assert "I am 74 and recently widowed" in ruth.notes
    assert ruth.goals == "Keep my savings safe and leave something for my grandchildren"
    assert (ruth.horizon_years, int(ruth.investable_usd), ruth.source_of_funds) == (10, 180000, "inheritance")


def test_calls_are_for_staff_only(client, ruth):
    assert client.get(f"/leads/{ruth.id}/calls").status_code == 401
    assert client.get(f"/leads/{ruth.id}/calls", headers=INVESTOR).status_code == 403
    assert client.post(f"/leads/{ruth.id}/calls/demo", json={"name": "pressure"}, headers=INVESTOR).status_code == 403
    assert client.get("/demo/calls/pressure.mp3", headers=INVESTOR).status_code == 403
    assert client.get(f"/leads/{ruth.id}/calls", headers=STAFF).json() == []
    assert client.get("/leads/nope/calls", headers=STAFF).status_code == 404


def test_the_pressure_call_is_read_flagged_and_lowers_ruths_trust(client, db, ruth):
    llm = answer(client, PRESSURE)
    r = client.post(f"/leads/{ruth.id}/calls/demo", json={"name": "pressure"}, headers=STAFF)
    assert r.status_code == 201, r.text
    call = r.json()
    assert set(call) == {"id", "filename", "source", "duration_s", "reading", "dropped", "applied", "created_at",
                         "created_by"}
    assert (call["filename"], call["source"], call["created_by"]) == ("pressure.mp3", "demo", "Daniel Okafor")
    kinds = {f["kind"] for f in call["reading"]["flags"]}
    assert {"promissory", "third_party_direction", "confusion"} <= kinds
    assert llm.calls[0]["attachments"][0].data == (CALLS / "pressure.mp3").read_bytes()
    db.expire_all()
    lead = client.get(f"/leads/{ruth.id}", headers=STAFF).json()
    assert "T08" in [s["code"] for s in lead["trust_signals"]]


def test_the_attack_call_is_not_offered_as_a_demo(client, ruth):
    answer(client, PRESSURE)
    assert client.post(f"/leads/{ruth.id}/calls/demo", json={"name": "attack"}, headers=STAFF).status_code == 422


def test_a_demo_call_is_analysed_only_on_its_own_lead(client, db, ruth, emma):
    llm = answer(client, PRESSURE)
    wrong = client.post(f"/leads/{emma.id}/calls/demo", json={"name": "pressure"}, headers=STAFF)
    assert wrong.status_code == 422 and "Ruth Alvarez" in wrong.json()["detail"]
    other = client.post(f"/leads/{ruth.id}/calls/demo", json={"name": "discovery"}, headers=STAFF)
    assert other.status_code == 422 and "Emma Walsh" in other.json()["detail"]
    assert llm.calls == [] and db.query(LeadCall).count() == 0
    assert "T08" not in [s["code"] for s in client.get(f"/leads/{emma.id}", headers=STAFF).json()["trust_signals"] or []]


def test_calls_list_newest_first(client, ruth):
    answer(client, PRESSURE)
    first = client.post(f"/leads/{ruth.id}/calls/demo", json={"name": "pressure"}, headers=STAFF).json()
    second = client.post(f"/leads/{ruth.id}/calls", files={"file": ("ruth.mp3", MP3, "audio/mpeg")},
                         headers=STAFF).json()
    listed = client.get(f"/leads/{ruth.id}/calls", headers=STAFF).json()
    assert [c["id"] for c in listed] == [second["id"], first["id"]]
    assert second["source"] == "upload" and second["filename"] == "ruth.mp3"


@pytest.mark.parametrize("name,data,mime", [("notes.txt", b"hello there", "text/plain"),
                                            ("fake.mp3", b"%PDF-1.7 a document", "audio/mpeg")])
def test_a_file_that_is_not_a_recording_is_refused(client, ruth, name, data, mime):
    llm = answer(client, PRESSURE)
    r = client.post(f"/leads/{ruth.id}/calls", files={"file": (name, data, mime)}, headers=STAFF)
    assert r.status_code == 422 and r.json()["detail"] == "This file is not an MP3, WAV, M4A or OGG recording."
    assert llm.calls == []


def test_a_recording_over_20_mb_is_refused(client, ruth):
    llm = answer(client, PRESSURE)
    big = MP3 + b"\x00" * (20 * 1024 * 1024)
    r = client.post(f"/leads/{ruth.id}/calls", files={"file": ("long.mp3", big, "audio/mpeg")}, headers=STAFF)
    assert r.status_code == 413 and "20 MB" in r.json()["detail"] and llm.calls == []


def test_a_silent_recording_is_refused_with_its_reason(client, db, ruth):
    answer(client, {**PRESSURE, "transcript": [], "flags": []})
    r = client.post(f"/leads/{ruth.id}/calls", files={"file": ("quiet.mp3", MP3, "audio/mpeg")}, headers=STAFF)
    assert r.status_code == 422 and r.json()["detail"] == "No speech was found in this recording."
    assert db.query(LeadCall).count() == 0


def test_a_paused_model_or_an_unreachable_gemini_is_a_503_in_plain_words(client, db, ruth):
    answer(client, error=LLMError("quota"))
    r = client.post(f"/leads/{ruth.id}/calls/demo", json={"name": "pressure"}, headers=STAFF)
    assert r.status_code == 503 and r.json()["detail"] == "Call analysis is unavailable right now."
    trip(db, "call_analyst", reason="It missed its bar in the live checks.", by="Live checks")
    db.commit()
    r = client.post(f"/leads/{ruth.id}/calls/demo", json={"name": "pressure"}, headers=STAFF)
    assert r.status_code == 503 and r.json()["detail"].startswith("Call analysis is paused: It missed its bar")


def test_applying_updates_writes_the_lead_once_and_rescores_it(client, db, emma, people):
    bus = InProcessEventBus()
    set_event_bus(bus)
    answer(client, DISCOVERY)
    call = client.post(f"/leads/{emma.id}/calls/demo", json={"name": "discovery"}, headers=STAFF).json()
    offered = {u["field"]: (u["current"], u["proposed"]) for u in call["reading"]["updates"]}
    assert offered == {"horizon_years": ("15", "12"), "monthly_usd": ("1500", "2000"),
                       "investable_usd": ("150000", "175000")}
    r = client.post(f"/leads/{emma.id}/calls/{call['id']}/apply", json={"fields": ["horizon_years", "monthly_usd"]},
                    headers=STAFF)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["lead"]["horizon_years"] == 12 and Decimal(body["lead"]["monthly_usd"]) == 2000
    assert Decimal(body["lead"]["investable_usd"]) == 150000  # not ticked, not written
    assert body["lead"]["lead_score"] is not None and body["lead"]["trust_score"] is not None
    assert [(a["field"], a["value"], a["by"]) for a in body["call"]["applied"]] == [
        ("horizon_years", "12", "Daniel Okafor"), ("monthly_usd", "2000", "Daniel Okafor")]
    assert body["applied"] == ["horizon_years", "monthly_usd"]
    events = [e for e in bus.history if e.type == "LeadUpdatedFromCall"]
    assert len(events) == 1 and events[0].payload["fields"] == ["horizon_years", "monthly_usd"]

    again = client.post(f"/leads/{emma.id}/calls/{call['id']}/apply", json={"fields": ["horizon_years"]},
                        headers=STAFF).json()
    assert again["applied"] == [] and len(again["call"]["applied"]) == 2  # the second apply is a no-op
    assert len([e for e in bus.history if e.type == "LeadUpdatedFromCall"]) == 1


def test_an_update_the_call_did_not_propose_cannot_be_applied(client, people, emma):
    answer(client, DISCOVERY)
    call = client.post(f"/leads/{emma.id}/calls/demo", json={"name": "discovery"}, headers=STAFF).json()
    r = client.post(f"/leads/{emma.id}/calls/{call['id']}/apply", json={"fields": ["goals"]}, headers=STAFF)
    assert r.status_code == 422 and "goals" in r.json()["detail"]
    assert client.post(f"/leads/{emma.id}/calls/{call['id']}/apply", json={"fields": ["bogus"]},
                       headers=STAFF).status_code == 422


def test_another_leads_call_cannot_be_applied(client, emma, ruth):
    answer(client, DISCOVERY)
    call = client.post(f"/leads/{emma.id}/calls/demo", json={"name": "discovery"}, headers=STAFF).json()
    r = client.post(f"/leads/{ruth.id}/calls/{call['id']}/apply", json={"fields": ["monthly_usd"]}, headers=STAFF)
    assert r.status_code == 404
    assert client.post(f"/leads/{emma.id}/calls/nope/apply", json={"fields": ["monthly_usd"]},
                       headers=STAFF).status_code == 404


def test_the_demo_audio_plays_for_staff(client, people):
    r = client.get("/demo/calls/pressure.mp3", headers=STAFF)
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
    assert r.content == (CALLS / "pressure.mp3").read_bytes()
    assert client.get("/demo/calls/discovery.mp3", headers=STAFF).status_code == 200
    assert client.get("/demo/calls/attack.mp3", headers=STAFF).status_code == 404
    assert client.get("/demo/calls/..%2Fcalls.mp3", headers=STAFF).status_code == 404


def test_offline_the_demo_call_reads_as_its_script_and_the_rules_still_flag_the_promise(client, ruth):
    client.app.dependency_overrides.pop(get_llm, None)  # the offline responder (llm_provider "fake")
    r = client.post(f"/leads/{ruth.id}/calls/demo", json={"name": "pressure"}, headers=STAFF)
    assert r.status_code == 201, r.text
    reading = r.json()["reading"]
    script = json.loads((CALLS / "pressure.json").read_text(encoding="utf-8"))
    assert [s["text"] for s in reading["transcript"]] == [line["text"] for line in script["lines"]]
    assert reading["summary"].startswith("Offline mode")
    assert [(f["kind"], f["source"]) for f in reading["flags"]] == [("promissory", "rules")]


def test_offline_an_uploaded_copy_of_a_demo_call_is_recognised_by_its_size(client, ruth):
    client.app.dependency_overrides.pop(get_llm, None)
    data = (CALLS / "discovery.mp3").read_bytes()
    r = client.post(f"/leads/{ruth.id}/calls", files={"file": ("renamed.mp3", data, "audio/mpeg")}, headers=STAFF)
    assert r.status_code == 201 and r.json()["reading"]["transcript"][0]["speaker"] == "Daniel"
    other = client.post(f"/leads/{ruth.id}/calls", files={"file": ("mine.mp3", MP3, "audio/mpeg")}, headers=STAFF)
    assert other.status_code == 201 and "Offline mode" in other.json()["reading"]["transcript"][0]["text"]
