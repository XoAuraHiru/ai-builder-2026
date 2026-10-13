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


# Task M3: reconciliation, Guardian, draft compliance, case checkers
from app.governance.evals.suites import case_reviewer, draft_compliance, pretrade_guardian, reconciler_agent  # noqa: E402


def test_the_rules_are_exact_and_the_scorer_is_mostly_right():
    result = reconciler_agent.rules_and_scorer(FREE)
    assert result.passed, result.metric
    assert "precision" in result.metric and "recall" in result.metric
    assert len(result.cases) == 10


def test_a_scorer_that_proposes_on_any_amount_hits_a_decoy(monkeypatch):
    import app.services.reconciliation as reconciliation

    monkeypatch.setattr(reconciliation, "FUZZY_MIN", 0.25)
    result = reconciler_agent.rules_and_scorer(FREE)
    assert result.passed is False
    assert "interest-equals-a-waiting-amount" in {c.case_id for c in result.cases if c.outcome == "fail"}


def test_pairs_are_read_from_matches_and_from_scorer_dicts():
    ids = {"l1": "L-1", "l2": "L-2", "r1": "I-1"}
    from app.models import ReconMatch

    match = ReconMatch(line_ids=["L-1"], instruction_ids=["I-1"], tier="fuzzy", confidence=0.8, evidence=[],
                       proposed_by="rules")
    assert reconciler_agent.pairs_of([match], ids) == {(frozenset({"l1"}), frozenset({"r1"}))}
    assert reconciler_agent.pairs_of([{"line_ids": ["L-1", "L-2"], "instruction_id": "I-1"}], ids) == {
        (frozenset({"l1", "l2"}), frozenset({"r1"}))}
    assert reconciler_agent.precision_recall(set(), {1}) == (None, 0.0)


def test_the_guardian_gives_every_golden_order_its_verdict():
    result = pretrade_guardian.golden_orders(FREE)
    assert result.passed and len(result.cases) == 6, [(c.case_id, c.actual) for c in result.cases if c.outcome != "pass"]
    assert {c.expected for c in result.cases} == {"proceed", "warn", "hold", "block"}


def test_the_draft_rules_catch_promises_and_spare_honest_sentences():
    result = draft_compliance.rules_on_phrases(FREE)
    assert result.passed and len(result.cases) == 10
    labels = [c["promissory"] for c in golden.load("draft_compliance/phrases")["cases"]]
    assert labels.count(True) == 5 and labels.count(False) == 5


def test_the_draft_suite_fails_without_the_negation_guard(monkeypatch):
    import app.services.compliance as compliance

    monkeypatch.setattr(compliance, "_negated", lambda text, start: False)
    assert draft_compliance.rules_on_phrases(FREE).passed is False


def test_the_case_checkers_catch_every_planted_fault():
    result = case_reviewer.checkers_catch_faults(FREE)
    assert result.passed and len(result.cases) == 4  # the clean review passes, and each of three faults is caught


def test_check_review_names_and_figures():
    from app.services.compliance_ai import check_review

    review = {"triage": "escalate", "triage_reason": "Three payments of $9,400 or more.",
              "narrative": [{"text": "Grace Li was paid by Marcus Okonkwo; Jane Doe approved it.", "evidence": ["e1", "x"]}],
              "questions": ["Did the Suspicious Activity Report team see the $1,000,000?"]}
    out = check_review(review, {"e1"}, {9400.0}, {"Grace Li", "Marcus Okonkwo"})
    assert out == {"dropped_citations": ["x"], "unsupported_figures": ["$1,000,000"], "unknown_names": ["Jane Doe"]}
