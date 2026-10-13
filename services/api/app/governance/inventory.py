"""The model inventory: every AI and quantitative model in Atrium, once, with what governs it.

A model's version is a short hash of the text that defines it (prompt templates, schemas, rules, committed model
files) and the model id it runs on, so any change to a prompt or a rule shows as a new version without anyone
having to remember to bump a number.
"""
import hashlib
import importlib
import inspect
import json
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings

APP_ROOT = Path(__file__).resolve().parents[1]  # services/api/app
KINDS = {"gemini_prompt": "Gemini prompt", "adk_agent": "ADK agent", "bigquery_ml": "BigQuery ML",
         "document_ai": "Document AI", "rules": "Rules"}
TIERS = ("high", "medium")


@dataclass(frozen=True)
class ModelSpec:
    key: str
    name: str
    kind: str
    tier: str
    owner: str  # the owning persona's email
    purpose: str
    human_gate: str
    fallback: str | None  # what runs while the breaker is open; None when nothing can stand in
    limitations: tuple[str, ...]
    sources: tuple[str, ...]  # "module:pkg.mod", "attr:pkg.mod:NAME" or "file:path/under/app"
    model_setting: str | None = None  # the Settings attribute naming the model id it runs on


DANIEL, MEI, OMAR = "daniel@atrium.demo", "mei@atrium.demo", "omar@atrium.demo"

MODELS: dict[str, ModelSpec] = {m.key: m for m in (
    ModelSpec("lead_score", "Lead Score", "bigquery_ml", "medium", DANIEL,
              "Ranks new leads by how likely they are to become clients, with the factors for and against.",
              "An advisor decides whom to call.", None,
              ("Trained on synthetic lead history, not on real outcomes.",
               "Goal fit comes from Gemini's reading of the lead, so the enrichment's errors reach the score."),
              ("file:ml/lead_model.json", "attr:app.ml.lead_features:features_for")),
    ModelSpec("lead_enrichment", "Lead enrichment", "gemini_prompt", "medium", DANIEL,
              "Reads a lead's form and notes into goals, suggested funds, inconsistencies and a next step.",
              "An advisor reads it before calling.", "Offline rules read the form instead.",
              ("Reads only what the lead wrote; it cannot check that it is true.",),
              ("attr:app.services.enrichment:PROMPT", "attr:app.services.enrichment:Enrichment"),
              "gemini_flash_model"),
    ModelSpec("trust_rules", "Trust Score stage 1", "rules", "high", DANIEL,
              "Scores fraud and identity risk at the lead stage from contact details, devices and documents.",
              "An advisor reviews; a blocking signal stops conversion.", None,
              ("Throwaway email domains are recognised from a fixed list.",
               "A device ring is seen only when the leads share a device id."),
              ("module:app.services.trust",)),
    ModelSpec("identity_proofing", "Identity check", "document_ai", "high", DANIEL,
              "Reads an identity document and checks it against the form and Document AI's fraud signals.",
              "An advisor reviews every finding.", None,
              ("Specimen cards only in this demo; no live identity documents are read.",),
              ("module:app.services.identity",), "docai_proofing_processor"),
    ModelSpec("draft_compliance", "Draft compliance check", "gemini_prompt", "high", OMAR,
              "Flags promissory or misleading language in client messages before an advisor sends them.",
              "The advisor edits and sends.", "The rules alone check the draft.",
              ("Rules catch known phrasings; Gemini covers the rest and can miss subtle claims.",),
              ("module:app.services.compliance",), "gemini_flash_model"),
    ModelSpec("statement_reader", "Statement reading", "document_ai", "high", MEI,
              "Reads bank statement PDFs into dated lines with amounts and sides.",
              "Operations decides every match.", "Statements are read as CSV only.",
              ("The parser labels some cells inconsistently; the side is taken from the narration and the lines are "
               "checked against the balances.",),
              ("attr:app.services.statements:extraction_from_document", "attr:app.services.statements:parse_csv"),
              "docai_statement_processor"),
    ModelSpec("narration_reader", "Narration reading", "gemini_prompt", "medium", MEI,
              "Reads each statement narration into a remitter name and a payment reference.",
              "Operations decides every match.", "Rules read the narrations.",
              ("A reference with several typos can be read as no reference.",),
              ("attr:app.services.statements:NORMALISE_PROMPT", "attr:app.services.statements:StatementReading"),
              "gemini_flash_model"),
    ModelSpec("reconciler_agent", "Reconciliation agent", "adk_agent", "high", MEI,
              "Proposes matches between deposits and waiting subscriptions that the rules could not settle.",
              "Operations accepts or rejects each proposal.", "The scorer proposes the strongest matches.",
              ("It proposes; it never matches. Split payments are found only among the open lines.",),
              ("module:app.agents.reconciler", "attr:app.services.reconciliation:score"), "gemini_flash_model"),
    ModelSpec("aml_scenarios", "AML scenarios", "rules", "high", OMAR,
              "Seven monitoring scenarios adapted to US practice, from structuring to linked round trips.",
              "The MLRO decides every alert.", None,
              ("Thresholds are fixed; amounts just outside them are not flagged by the rules.",),
              ("module:app.services.aml",)),
    ModelSpec("aml_anomaly", "AML anomaly model", "bigquery_ml", "medium", OMAR,
              "A k-means model trained in BigQuery ML that flags accounts unlike their peers.",
              "The MLRO decides every alert.", "The scenarios alone raise alerts.",
              ("Trained on synthetic account behaviour.",),
              ("file:ml/aml_model.json", "attr:app.ml.aml_model:AmlModel")),
    ModelSpec("case_reviewer", "Case review", "gemini_prompt", "high", OMAR,
              "Suggests a triage, a case narrative citing the evidence, and questions for one alert.",
              "The MLRO decides.", "Case reviews pause; the MLRO decides from the evidence.",
              ("It may cite only evidence ids it was given; uncited claims are dropped.",),
              ("attr:app.services.compliance_ai:REVIEW_PROMPT", "attr:app.services.compliance_ai:AlertReview"),
              "gemini_pro_model"),
    ModelSpec("pretrade_guardian", "Pre-trade Guardian", "rules", "high", DANIEL,
              "Checks every order for suitability, concentration, liquidity, size, wash sales and takeover risk.",
              "The investor decides; an advisor decides on held orders.", "The rules run without the explanation.",
              ("Uses the latest quote; a fast market can move past it.",),
              ("module:app.services.guardian", "attr:app.services.order_ai:explain_order"), "gemini_flash_model"),
    ModelSpec("held_order_reviewer", "Held-order review note", "gemini_prompt", "medium", DANIEL,
              "Writes the advisor's review note on an order the Guardian held.",
              "The advisor releases or rejects the order.", "Review notes pause.",
              ("It sees the order and the account, not the client's circumstances beyond them.",),
              ("attr:app.services.order_ai:REVIEW_PROMPT", "attr:app.services.order_ai:ReviewNote"),
              "gemini_pro_model"),
    ModelSpec("investor_copilot", "Investor Copilot", "adk_agent", "medium", DANIEL,
              "Answers an investor's questions from their own portfolio, the engines and the fund documents.",
              "The investor decides; it never places an order.", "The Copilot pauses.",
              ("Answers only from its tools and the fund documents.",),
              ("module:app.agents.investor",), "gemini_flash_model"),
    ModelSpec("proposal_writer", "Proposal", "gemini_prompt", "medium", DANIEL,
              "Writes a personalised proposal whose every figure comes from the engines.",
              "The advisor reviews and sends it.", "Proposals pause.",
              ("Figures not found in the engines' output are flagged, not removed.",),
              ("attr:app.services.proposal:PROMPT",), "gemini_pro_model"),
    ModelSpec("scenario_mapper", "Scenario mapping", "gemini_prompt", "medium", DANIEL,
              "Turns a scenario written in plain English into explicit, bounded shocks, grounded with Google Search.",
              "The investor sees every shock and can change it.", "Only the history replays are offered.",
              ("Shocks are judgements, not forecasts; the engine's arithmetic is exact, the shocks are not.",),
              ("module:app.services.scenarios",), "gemini_flash_model"),
    ModelSpec("call_analyst", "Call analysis", "gemini_prompt", "high", DANIEL,
              "Turns a recorded client call into a transcript, a summary, proposed lead updates and conduct flags.",
              "The advisor applies each update; flags go to the advisor and compliance.", "Call analysis pauses.",
              ("A flag whose quote is not in the transcript is dropped, so a misheard quote can hide a real issue.",),
              ("module:app.services.calls",), "gemini_flash_model"),
    ModelSpec("ring_narrator", "Ring narrative", "gemini_prompt", "medium", OMAR,
              "Explains how a fraud ring's members connect and what pattern it resembles.",
              "The MLRO decides whether to open a case.", "Rings show without a narrative.",
              ("It explains links the graph found; it cannot find new ones.",),
              ("module:app.services.rings",), "gemini_flash_model"),
)}


def _source_text(source: str) -> str:
    kind, _, ref = source.partition(":")
    try:
        if kind == "file":
            return (APP_ROOT / ref).read_text(encoding="utf-8")
        if kind == "module":
            return inspect.getsource(importlib.import_module(ref))
        if kind == "attr":
            module, _, name = ref.rpartition(":")
            value = getattr(importlib.import_module(module), name)
            if isinstance(value, str):
                return value
            if hasattr(value, "model_json_schema"):
                return json.dumps(value.model_json_schema(), sort_keys=True)
            return inspect.getsource(value)
    except (ImportError, AttributeError, OSError, TypeError):
        return f"missing {source}"
    raise ValueError(f"Unknown source kind in {source!r}")


def model_id(spec: ModelSpec) -> str | None:
    return getattr(get_settings(), spec.model_setting, None) if spec.model_setting else None


def version(spec: ModelSpec) -> str:
    digest = hashlib.sha256()
    for source in spec.sources:
        digest.update(f"{source}\0{_source_text(source)}\0".encode())
    digest.update((model_id(spec) or "").encode())
    return digest.hexdigest()[:10]


def versions() -> dict[str, str]:
    return {key: version(spec) for key, spec in MODELS.items()}


def missing_sources(spec: ModelSpec) -> list[str]:
    return [s for s in spec.sources if _source_text(s) == f"missing {s}"]
