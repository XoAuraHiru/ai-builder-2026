"""Testing left artefacts in the demo data that the fraud ring radar reads as rings: a device shared by every persona
a smoke test touched, and Atrium's own sample ID card uploaded on several leads."""
import hashlib
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.models import Account, AccountDevice, IdentityCheck, Person
from app.ops.cleanup_artefacts import main, shared_device_rows
from app.seed.rings import RING_DEVICE
from app.services.devices import device_hash
from app.services.identity import SAMPLE_CARD_SHA256
from app.services.rings import build_graph

WEB_DEMO = Path(__file__).resolve().parents[3] / "apps" / "web" / "public" / "demo"


def _account(db, name: str, number: str) -> Account:
    person = Person(kind="investor", full_name=name, email=f"{number.lower()}@atrium.demo")
    db.add(person)
    db.flush()
    account = Account(person_id=person.id, number=number, opened_on=date(2024, 10, 1))
    db.add(account)
    db.flush()
    return account


def test_the_sample_cards_the_web_offers_are_the_ones_the_api_knows():
    on_the_web = {hashlib.sha256((WEB_DEMO / f).read_bytes()).hexdigest()
                  for f in ("specimen-match.png", "specimen-mismatch.png")}
    assert on_the_web == SAMPLE_CARD_SHA256


def test_a_sample_card_on_two_leads_is_no_ring(db, make_lead):
    a = make_lead(full_name="James Patel", email="james@example.test", phone="+14155550101")
    b = make_lead(full_name="Linda Morales", email="linda@example.test", phone="+14155550102")
    sample = next(iter(SAMPLE_CARD_SHA256))
    for lead in (a, b):
        db.add(IdentityCheck(lead_id=lead.id, mime_type="image/png", size_bytes=10, sha256=sample,
                             extracted={"document_type": "other", "document_number": "SPECIMEN-0001"}, findings=[],
                             source="test"))
    db.flush()
    assert not [i for i in build_graph(db).identifiers.values() if i.kind == "document"]


def test_a_real_document_on_two_leads_still_links_them(db, make_lead):
    a = make_lead(full_name="James Patel", email="james@example.test", phone="+14155550101")
    b = make_lead(full_name="Linda Morales", email="linda@example.test", phone="+14155550102")
    for lead in (a, b):
        db.add(IdentityCheck(lead_id=lead.id, mime_type="image/png", size_bytes=10, sha256="0" * 64,
                             extracted={"document_type": "passport", "document_number": "P-998877"}, findings=[],
                             source="test"))
    db.flush()
    assert [i for i in build_graph(db).identifiers.values() if i.kind == "document"]


def test_cleanup_finds_devices_shared_across_accounts_but_keeps_the_seeded_ring_device(db):
    tom, priya, sofia, lucas = (_account(db, n, f"ACC-90{k}") for k, n in
                                enumerate(("Tom Becker", "Priya Raman", "Sofia Rossi", "Lucas Moreau")))
    smoke = device_hash("smoke-1234")
    db.add_all([AccountDevice(account_id=tom.id, device_hash=smoke, label="Unknown browser"),
                AccountDevice(account_id=priya.id, device_hash=smoke, label="Unknown browser"),
                AccountDevice(account_id=tom.id, device_hash=device_hash("seed-device:tom"), label="Chrome on Windows"),
                AccountDevice(account_id=sofia.id, device_hash=device_hash(RING_DEVICE), label="Chrome on Windows"),
                AccountDevice(account_id=lucas.id, device_hash=device_hash(RING_DEVICE), label="Chrome on Windows")])
    db.flush()
    found = shared_device_rows(db)
    assert {(r.account_id, r.device_hash) for r in found} == {(tom.id, smoke), (priya.id, smoke)}


def test_cleanup_is_a_dry_run_unless_asked_to_apply(db, capsys):
    tom, priya = _account(db, "Tom Becker", "ACC-0910"), _account(db, "Priya Raman", "ACC-0911")
    smoke = device_hash("smoke-5678")
    db.add_all([AccountDevice(account_id=tom.id, device_hash=smoke, label="Unknown browser"),
                AccountDevice(account_id=priya.id, device_hash=smoke, label="Unknown browser")])
    db.commit()
    assert main([], db=db) == 2 and len(db.scalars(select(AccountDevice)).all()) == 2
    assert "Dry run" in capsys.readouterr().out
    assert main(["--apply"], db=db) == 2 and db.scalars(select(AccountDevice)).all() == []
    assert main(["--apply"], db=db) == 0  # running it again finds nothing
