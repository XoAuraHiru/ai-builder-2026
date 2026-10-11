"""Offline responders so the app runs end to end without Gemini credentials (local dev, demos without network)."""
import re

from app.ai.llm import FakeLLM

_GOALS = [("retire|retirement|grow|growth|long term|wealth", "growth", ["ATR-GRW", "ATR-BAL"]),
          ("income|dividend|cash flow", "income", ["ATR-INC", "ATR-DIV"]),
          ("safe|emergency|preserve|short term", "capital_preservation", ["ATR-CASH"]),
          ("tech|technology", "thematic_tech", ["ATR-TEC", "ATR-GRW"]),
          ("global|international|world", "global", ["ATR-GLB"])]


def _enrich(prompt: str) -> dict:
    lead_text = prompt.split("<lead>")[-1].lower()
    category, funds = "balanced", ["ATR-BAL"]
    for pattern, cat, codes in _GOALS:
        if re.search(pattern, lead_text):
            category, funds = cat, codes
            break
    return {"goal_category": category, "goals_summary": "Offline summary: goals captured from the form.",
            "suggested_funds": funds, "stated_risk_appetite": "medium", "consistency_issues": [],
            "text_authenticity": "natural", "next_best_action": "Call to confirm goals and timeline.",
            "confidence": 0.5}


def offline_llm() -> FakeLLM:
    return FakeLLM({
        "lead_enrichment": _enrich,
        "compliance_review": {"findings": []},
        "identity_extraction": {"document_type": "other", "full_name": None, "date_of_birth": None,
                                "document_number": None, "expiry_date": None, "issuing_country": None,
                                "confidence": 0.0},
    }, model="offline")
