"""Identity check: the saved Document AI ID Proofing outputs of the two specimen cards map to the right fields and
findings (free), and the same two cards sent through Document AI give the same (live, with documents only)."""
from datetime import date

from app.governance import golden
from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, every_case, run_case, suite
from app.models import Lead
from app.services.identity import fields_from_document, get_proofing, identity_findings


def _document(name: str):
    from google.cloud import documentai

    text = golden.path(f"identity_proofing/{name}").read_text(encoding="utf-8")
    return documentai.Document.from_json(text, ignore_unknown_fields=True)


def _grade(c: dict, extracted, signals) -> CaseResult:
    lead = Lead(full_name=c["lead"]["full_name"], email="specimen@example.test", country="US", source="web",
                goals="", horizon_years=1, device_id="golden")
    findings = sorted({f["code"] for f in identity_findings(lead, extracted, signals, date.fromisoformat(c["today"]))})
    actual = {"full_name": extracted.full_name, "date_of_birth": extracted.date_of_birth,
              "expiry_date": extracted.expiry_date, "findings": findings}
    expected = {**c["expect"], "findings": sorted(c["expect"]["findings"])}
    wrong = [k for k in expected if actual.get(k) != expected[k]]
    detail = c["why"] if not wrong else f"Wrong {', '.join(wrong)}. {c['why']}"
    return CaseResult(c["id"], "fail" if wrong else "pass", expected=expected, actual=actual, detail=detail)


@suite("identity_proofing")
def saved_outputs(ctx: EvalContext) -> SuiteResult:
    cases = []
    for c in golden.load("identity_proofing/cases")["cases"]:
        def check(c=c):
            extracted, signals = fields_from_document(_document(c["document"]))
            return _grade(c, extracted, signals)
        cases.append(run_case(c["id"], check))
    return every_case("identity_proofing", "golden", "free", cases,
                      bar="Both saved outputs give the right name, birth date and expiry, and the mismatch is found")


@suite("identity_proofing", tier="live", needs_documents=True)
def live_cards(ctx: EvalContext) -> SuiteResult:
    proofing = get_proofing()
    cases = []
    for c in golden.load("identity_proofing/cases")["cases"]:
        def check(c=c):
            if proofing is None or not hasattr(proofing, "read"):
                return CaseResult(c["id"], "error", detail="Document AI ID Proofing is not configured here.")
            try:
                extracted, signals = proofing.read(golden.path(f"identity_proofing/{c['image']}").read_bytes(),
                                                   "image/png")
            except Exception as e:  # an outage or a quota is no verdict on the model
                return CaseResult(c["id"], "error", detail=f"Document AI could not be reached: {e}")
            return _grade(c, extracted, signals)
        cases.append(run_case(c["id"], check))
    return every_case("identity_proofing", "golden", "live", cases,
                      bar="Both cards through Document AI give the right name, birth date and expiry, and the mismatch "
                          "is found")
