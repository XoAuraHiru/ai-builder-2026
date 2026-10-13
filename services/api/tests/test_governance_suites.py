"""Free-tier golden suites: each passes on the committed code, and each fails when its model is broken."""
import pytest

from app.governance import golden
from app.governance.evals.framework import EvalContext
from app.governance.evals.suites import aml_scenarios, lead_score, trust_rules

FREE = EvalContext(tier="free")


def test_every_golden_case_says_why_its_answer_is_right():
    for name in ("lead_score/twins", "trust_rules/stories", "aml_scenarios/cases"):
        data = golden.load(name)
        assert data["cases"] and all(c.get("why") for c in data["cases"]), name


def test_a_golden_file_with_a_case_missing_its_why_is_refused(tmp_path, monkeypatch):
    (tmp_path / "bad.json").write_text('{"cases": [{"id": "a", "why": "fine"}, {"id": "b"}]}', encoding="utf-8")
    monkeypatch.setattr(golden, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="b"):
        golden.load("bad")


def test_the_stronger_twin_always_outscores_the_weaker():
    result = lead_score.twin_pairs(FREE)
    assert result.passed and len(result.cases) == 8, [c.detail for c in result.cases if c.outcome != "pass"]


def test_twins_fail_when_the_model_ranks_backwards(monkeypatch):
    monkeypatch.setattr(lead_score, "score_lead", lambda lead, enrichment: (100 - int(lead.investable_usd > 50000) * 60, {}))
    assert lead_score.twin_pairs(FREE).passed is False


def test_the_demo_fraud_stories_are_caught_and_genuine_leads_stay_clear():
    result = trust_rules.demo_stories(FREE)
    assert result.passed, [c.detail for c in result.cases if c.outcome != "pass"]
    assert {c.case_id for c in result.cases} >= {"alex-mercer", "device-ring", "m-chen"}
    assert len(result.cases) == 9


def test_the_stories_fail_when_the_throwaway_list_is_emptied(monkeypatch):
    import app.services.trust as trust

    monkeypatch.setattr(trust, "DISPOSABLE_DOMAINS", frozenset())
    assert trust_rules.demo_stories(FREE).passed is False


def test_each_aml_scenario_fires_on_its_case_and_not_on_its_near_miss():
    result = aml_scenarios.positives_and_near_misses(FREE)
    assert result.passed and len(result.cases) == 14, [c.detail for c in result.cases if c.outcome != "pass"]
    assert {c["scenario"] for c in golden.load("aml_scenarios/cases")["cases"]} == set(aml_scenarios.SCENARIOS)


def test_a_scenario_that_never_fires_fails_its_positive(monkeypatch):
    monkeypatch.setitem(aml_scenarios.SCENARIOS, "structuring", lambda db, today: [])
    result = aml_scenarios.positives_and_near_misses(FREE)
    assert [c.case_id for c in result.cases if c.outcome == "fail"] == ["structuring-positive"]


# Task M2: documents
from app.governance.evals.suites import identity_proofing, statement_reader  # noqa: E402


def test_every_golden_file_with_cases_says_why():
    found = []
    for path in sorted(golden.ROOT.rglob("*.json")):
        name = path.relative_to(golden.ROOT).with_suffix("").as_posix()
        data = golden.load(name)
        if "cases" in data:
            found.append(name)
    assert {"statement_reader/expected", "identity_proofing/cases"} <= set(found)


def test_the_saved_statement_maps_to_its_golden_lines_and_balances():
    result = statement_reader.saved_document(FREE)
    assert result.passed, [c.detail for c in result.cases if c.outcome != "pass"]
    assert len(result.cases) == 11 and result.cases[-1].case_id == "balances"


def test_the_statement_suite_fails_when_the_side_is_taken_from_the_labels(monkeypatch):
    import app.services.statements as statements

    monkeypatch.setattr(statements, "_side", lambda props, description: (
        "deposit" if any(n.startswith("transaction_deposit") and not n.endswith(("_date", "_description"))
                         for n in props) else "withdrawal"))
    result = statement_reader.saved_document(FREE)
    assert result.passed is False
    assert {c.case_id for c in result.cases if c.outcome == "fail"} >= {"line-6", "line-9", "balances"}


def test_messy_csvs_parse_to_their_golden_lines():
    result = statement_reader.messy_csvs(FREE)
    assert result.passed and len(result.cases) == 3, [c.detail for c in result.cases if c.outcome != "pass"]


def test_the_saved_identity_outputs_map_to_the_right_fields_and_findings():
    result = identity_proofing.saved_outputs(FREE)
    assert result.passed and len(result.cases) == 2, [(c.detail, c.actual) for c in result.cases if c.outcome != "pass"]


def test_document_ai_saying_not_an_id_is_a_finding(make_lead):
    from datetime import date

    from app.services.identity import ExtractedId, FraudSignals, identity_findings

    extracted = ExtractedId(document_type="other", full_name="Ava Thompson", confidence=0.9)
    found = identity_findings(make_lead(), extracted, FraudSignals(is_identity_document="NOT_AN_ID"), date(2026, 10, 13))
    assert [(f["code"], f["source"]) for f in found] == [("I00", "documentai")]


def test_the_live_cards_go_through_document_ai_proofing(monkeypatch):
    from app.config import Settings
    from app.services.identity import DocumentAIProofing

    saved = {}
    for case in golden.load("identity_proofing/cases")["cases"]:
        saved[golden.path(f"identity_proofing/{case['image']}").read_bytes()] = \
            golden.path(f"identity_proofing/{case['document']}").read_text(encoding="utf-8")

    class Client:
        def processor_path(self, project, location, processor):
            return f"projects/{project}/locations/{location}/processors/{processor}"

        def process_document(self, request):
            from google.cloud import documentai

            document = documentai.Document.from_json(saved[request.raw_document.content], ignore_unknown_fields=True)
            return documentai.ProcessResponse(document=document)

    proofing = DocumentAIProofing(Settings(_env_file=None, gcp_project="p", docai_proofing_processor="abc"),
                                  client=Client())
    monkeypatch.setattr(identity_proofing, "get_proofing", lambda: proofing)
    result = identity_proofing.live_cards(EvalContext(tier="live", with_documents=True))
    assert result.passed and len(result.cases) == 2, [c.detail for c in result.cases]
    monkeypatch.setattr(identity_proofing, "get_proofing", lambda: None)
    unconfigured = identity_proofing.live_cards(EvalContext(tier="live", with_documents=True))
    assert unconfigured.passed is False and unconfigured.counts["error"] == 2
