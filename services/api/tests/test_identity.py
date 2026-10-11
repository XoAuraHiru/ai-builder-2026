from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.ai.llm import FakeLLM, get_llm
from app.config import Settings
from app.models import AIDecision, IdentityCheck
from app.services.identity import (DocumentAIProofing, ExtractedId, FraudSignals, get_proofing, identity_findings,
                                   names_match)

STAFF = {"X-Dev-User": "daniel@atrium.demo"}
TODAY = date(2026, 10, 12)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


def extracted(**kw):
    base = dict(document_type="drivers_license", full_name="Ava Thompson", date_of_birth="1990-04-02",
                document_number="D1234567", expiry_date="2030-01-01", issuing_country="US", confidence=0.95)
    return ExtractedId(**{**base, **kw})


@pytest.mark.parametrize("a,b,expected", [
    ("Priya Raman", "RAMAN, PRIYA", True), ("Priya Raman", "Priya K. Raman", True),
    ("John Smith", "Jon Smith", True), ("Priya Raman", "Emily Walters", False), ("Ava Thompson", "", False)])
def test_name_match_ignores_order_case_and_punctuation(a, b, expected):
    assert names_match(a, b) is expected


def test_matching_valid_document_has_no_findings(make_lead):
    assert identity_findings(make_lead(), extracted(), None, TODAY) == []


def test_findings_flag_mismatch_expiry_and_minor(make_lead):
    found = identity_findings(make_lead(), extracted(full_name="Emily Walters", expiry_date="2024-05-01",
                                                     date_of_birth="2012-01-01"), None, TODAY)
    by_code = {f["code"]: f for f in found}
    assert set(by_code) == {"I01", "I02", "I03"} and by_code["I02"]["blocking"] is True
    assert "Emily Walters" in by_code["I01"]["evidence"]


def test_documentai_signals_become_findings(make_lead):
    signals = FraudSignals(is_identity_document="PASS", suspicious_words="INCONCLUSIVE",
                           image_manipulation="POSSIBLE_IMAGE_MANIPULATION", online_duplicate="POSSIBLE_ONLINE_DUPLICATE")
    found = identity_findings(make_lead(), extracted(), signals, TODAY)
    assert {f["code"] for f in found} == {"I04", "I05"} and all(f["blocking"] for f in found)
    not_id = identity_findings(make_lead(email="b@example.test"), extracted(),
                               FraudSignals(is_identity_document="FAIL"), TODAY)
    assert [f["code"] for f in not_id] == ["I00"]


def test_documentai_proofing_maps_entities():
    entities = [SimpleNamespace(type_="fraud_signals_is_identity_document", mention_text="PASS"),
                SimpleNamespace(type_="fraud_signals_image_manipulation", mention_text="POSSIBLE_IMAGE_MANIPULATION"),
                SimpleNamespace(type_="evidence_hostname", mention_text="example.com")]

    class Client:
        def processor_path(self, project, location, processor):
            return f"projects/{project}/locations/{location}/processors/{processor}"

        def process_document(self, request):
            self.request = request
            return SimpleNamespace(document=SimpleNamespace(entities=entities))

    client = Client()
    proofing = DocumentAIProofing(Settings(_env_file=None, gcp_project="p", docai_proofing_processor="abc"), client=client)
    signals = proofing.proof(PNG, "image/png")
    assert signals.is_identity_document == "PASS" and signals.image_manipulation == "POSSIBLE_IMAGE_MANIPULATION"
    assert signals.online_duplicate is None and client.request.name.endswith("/processors/abc")


@pytest.fixture()
def id_client(client):
    fake = FakeLLM({"identity_extraction": extracted(full_name="Emily Walters").model_dump()})
    client.app.dependency_overrides[get_llm] = lambda: fake
    client.app.dependency_overrides[get_proofing] = lambda: None
    yield client, fake


def test_upload_rejects_wrong_type_and_size_before_any_ai_call(id_client, people, make_lead):
    client, fake = id_client
    lead = make_lead()
    r = client.post(f"/leads/{lead.id}/documents", files={"file": ("a.txt", b"hello", "text/plain")}, headers=STAFF)
    assert r.status_code == 415
    big = b"\x89PNG" + b"0" * (5 * 1024 * 1024 + 1)
    r = client.post(f"/leads/{lead.id}/documents", files={"file": ("a.png", big, "image/png")}, headers=STAFF)
    assert r.status_code == 413 and fake.calls == []


def test_upload_extracts_records_and_updates_trust(id_client, db, people, make_lead):
    client, fake = id_client
    lead = make_lead()
    r = client.post(f"/leads/{lead.id}/documents", files={"file": ("id.png", PNG, "image/png")}, headers=STAFF)
    assert r.status_code == 201, r.text
    body = r.json()
    assert [f["code"] for f in body["findings"]] == ["I01"] and body["trust_band"] == "review"
    assert body["source"] == "gemini" and fake.calls[0]["attachments"][0].mime_type == "image/png"
    check = db.scalar(select(IdentityCheck))
    assert len(check.sha256) == 64 and not hasattr(check, "content")
    assert db.scalar(select(AIDecision).where(AIDecision.purpose == "identity_extraction")) is not None


def test_upload_is_staff_only(id_client, people, make_lead):
    client, _ = id_client
    lead = make_lead()
    r = client.post(f"/leads/{lead.id}/documents", files={"file": ("id.png", PNG, "image/png")},
                    headers={"X-Dev-User": "priya@atrium.demo"})
    assert r.status_code == 403
