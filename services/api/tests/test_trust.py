from datetime import timedelta

from app.models import IdentityCheck
from app.models.base import utcnow
from app.services.trust import apply_trust, assess_trust


def codes(report):
    return [s.code for s in report.signals]


def test_clean_lead_is_clear(db, make_lead):
    report = assess_trust(db, make_lead(), {"consistency_issues": [], "text_authenticity": "natural"}, None)
    assert (report.score, report.band, report.signals, report.blocked) == (100, "clear", [], False)


def test_disposable_email(db, make_lead):
    report = assess_trust(db, make_lead(email="x@mailinator.com"), None, None)
    assert codes(report) == ["T01"] and report.score == 75 and report.band == "review"


def test_phone_format_and_country(db, make_lead):
    assert codes(assess_trust(db, make_lead(phone="555-1234"), None, None)) == ["T02"]
    assert codes(assess_trust(db, make_lead(phone="+447700900123", email="uk@example.test"), None, None)) == ["T03"]


def test_duplicate_contact_names_the_other_lead(db, make_lead):
    first = make_lead()
    second = make_lead(email="other@example.test")  # same phone
    report = assess_trust(db, second, None, None)
    assert codes(report) == ["T04"] and first.id in report.signals[0].evidence


def test_device_velocity_counts_only_last_24_hours(db, make_lead):
    old = make_lead(email="o@example.test", phone=None, device_id="dev-ring-0001")
    old.created_at = utcnow() - timedelta(days=3)
    db.commit()
    make_lead(email="p@example.test", phone=None, device_id="dev-ring-0001")
    third = make_lead(email="q@example.test", phone=None, device_id="dev-ring-0001")
    assert "T05" not in codes(assess_trust(db, third, None, None))
    fourth = make_lead(email="r@example.test", phone=None, device_id="dev-ring-0001")
    report = assess_trust(db, fourth, None, None)
    assert "T05" in codes(report) and "3 leads" in report.signals[codes(report).index("T05")].evidence


def test_consistency_issue_weights_are_capped(db, make_lead):
    issues = [{"field": "x", "issue": f"problem {i}", "severity": "high"} for i in range(4)]
    report = assess_trust(db, make_lead(), {"consistency_issues": issues, "text_authenticity": "natural"}, None)
    assert sum(s.weight for s in report.signals if s.code == "T06") == -25


def test_generated_text(db, make_lead):
    report = assess_trust(db, make_lead(), {"consistency_issues": [], "text_authenticity": "likely_generated"}, None)
    assert codes(report) == ["T07"] and report.score == 90


def test_identity_findings_flow_in_and_blocking_sets_band(db, make_lead):
    lead = make_lead()
    check = IdentityCheck(lead_id=lead.id, mime_type="image/png", size_bytes=10, sha256="0" * 64, extracted={},
                          fraud_signals=None, source="gemini", findings=[
                              {"code": "I04", "label": "Possible image manipulation", "weight": -40,
                               "evidence": "Document AI", "source": "documentai", "blocking": True}])
    report = assess_trust(db, lead, None, check)
    assert report.band == "blocked" and report.blocked and report.score == 60


def test_score_floor_is_zero_and_order_is_stable(db, make_lead):
    issues = [{"field": "x", "issue": "bad", "severity": "high"}] * 2
    lead = make_lead(email="z@yopmail.com", phone="12")
    report = assess_trust(db, lead, {"consistency_issues": issues, "text_authenticity": "likely_generated"}, None)
    assert report.score >= 0 and codes(report) == sorted(codes(report), key=lambda c: (c[0], int(c[1:])))


def test_apply_trust_writes_fields_and_emits_on_change(db, make_lead):
    from app.events import InProcessEventBus, set_event_bus

    bus = InProcessEventBus()
    set_event_bus(bus)
    lead = make_lead(email="x@mailinator.com")
    apply_trust(db, lead)
    assert lead.trust_score == 75 and lead.trust_band == "review" and lead.trust_signals[0]["code"] == "T01"
    apply_trust(db, lead)
    assert [e.type for e in bus.history].count("TrustScoreChanged") == 1
