"""Offline responders so the app runs end to end without Gemini credentials (local dev, demos without network)."""
import re

from app.ai.llm import FakeLLM

_GOALS = [("retire|retirement|grow|growth|long term|wealth", "growth", ["ATR-GRW", "ATR-BAL"]),
          ("income|dividend|cash flow", "income", ["ATR-INC", "ATR-DIV"]),
          ("safe|emergency|preserve|short term", "capital_preservation", ["ATR-CASH"]),
          ("tech|technology", "thematic_tech", ["ATR-TEC", "ATR-GRW"]),
          ("global|international|world", "global", ["ATR-GLB"])]
OFFLINE = "Offline mode: connect Gemini to write this from the cited documents and the engines' figures."


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


def _narrative(prompt: str) -> dict:
    return {"headline": "Offline mode: connect Gemini for a written reading of these figures.",
            "paragraphs": ["Every figure on this page comes from Atrium's deterministic engines. When Gemini is "
                           "connected, it adds a plain-English reading here."],
            "cautions": ["Simulations and past performance are not guarantees."]}


def _risk_chat(prompt: str) -> dict:
    """Best-effort keyword extraction from the investor's latest message."""
    conversation = prompt.split("<conversation>")[-1].split("</conversation>")[0]
    said = [line[5:].lower() for line in conversation.strip().splitlines() if line.startswith("user:")]
    text = said[-1] if said else ""
    answers: dict = {}
    if m := re.search(r"(\d+)\s*(?:years?|yrs?)", text):
        answers["horizon_years"] = int(m.group(1))
    if m := re.search(r"(\d+)\s*%", text):
        answers["max_loss_pct"] = int(m.group(1))
    for words, key, value in (
            (("buy more",), "reaction_to_drop", "buy_more"), (("sell everything", "sell all"), "reaction_to_drop", "sell_all"),
            (("sell some",), "reaction_to_drop", "sell_some"), (("hold", "wait"), "reaction_to_drop", "hold"),
            (("most of it",), "withdraw_within_2y", "most"), (("some of it",), "withdraw_within_2y", "some"),
            (("none of it", "won't need", "not touch"), "withdraw_within_2y", "none"),
            (("no experience", "beginner", "never invested"), "experience", "none"),
            (("experienced", "a lot of experience"), "experience", "experienced"),
            (("some experience", "a little"), "experience", "some")):
        if key not in answers and any(w in text for w in words):
            answers[key] = value
    return {"answers": answers, "reply": ""}


def _passage_ids(prompt: str) -> list[str]:
    return re.findall(r'<passage id="([^"]+)"', prompt)


def _fund_fit(prompt: str) -> dict:
    return {"headline": "Offline mode: connect Gemini for a personal reading of this fund.",
            "points": [{"text": "The fund's objective, fees and risks are in the documents cited here.",
                        "citations": _passage_ids(prompt)[:2]}],
            "caution": "Past performance does not predict future returns."}


def _proposal(prompt: str) -> dict:
    ids = _passage_ids(prompt)
    firm = [i for i in ids if i.startswith("ATRIUM#")][:1]
    funds = [i for i in ids if not i.startswith("ATRIUM#")][:2]
    keys = [("why_atrium", "Why Atrium", firm), ("recommendation", "Our suggestion", funds),
            ("projection", "What it could become", ["projection"]), ("fees", "Fees", funds[:1]),
            ("risks", "Risks", funds[:1])]
    return {"sections": [{"key": k, "heading": h, "body": OFFLINE, "citations": c} for k, h, c in keys]}


def _review(prompt: str) -> dict:
    return {"summary": "Offline mode: connect Gemini Pro for a review note on this held order.",
            "considerations": ["Every check and figure on this page comes from the Guardian's fixed rules."],
            "questions_for_client": ["Did you place this order yourself, and what is the money for?"],
            "suggestion": "call_client", "suggestion_reason": "Offline mode cannot weigh the evidence for you."}


def _statement(prompt: str) -> dict:
    """Read every numbered line with the same rules the app falls back to."""
    from app.services.statements import rule_reading

    listing = prompt.split("<lines>")[-1].split("</lines>")[0]
    out = []
    for raw in listing.strip().splitlines():
        number, _, rest = raw.partition(". ")
        if number.isdigit():
            description = rest.split(" ", 2)[-1]
            out.append(rule_reading(int(number), description).model_dump())
    return {"lines": out}


def offline_llm() -> FakeLLM:
    return FakeLLM({
        "lead_enrichment": _enrich,
        "compliance_review": {"findings": []},
        "identity_extraction": {"document_type": "other", "full_name": None, "date_of_birth": None,
                                "document_number": None, "expiry_date": None, "issuing_country": None,
                                "confidence": 0.0},
        "whatif_narrative": _narrative, "risk_narrative": _narrative, "xray_narrative": _narrative,
        "risk_profile_chat": _risk_chat, "fund_fit": _fund_fit, "proposal": _proposal,
        "order_explainer": _narrative, "held_order_review": _review,
        "statement_normalise": _statement,
    }, model="offline")
