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


def _case(prompt: str) -> dict:
    ids = re.findall(r'"id": "([^"]+)"', prompt.split("<evidence>")[-1].split("</evidence>")[0])
    return {"triage": "request_information",
            "triage_reason": "Offline mode: connect Gemini Pro for a suggested triage.",
            "narrative": [{"text": "Offline mode: the alert's evidence is listed above; Gemini Pro drafts the case "
                                   "narrative when connected.", "evidence": ids[:2]}],
            "questions": ["What does the client say about these movements?"]}


def _brief(prompt: str) -> dict:
    return {"headline": "Offline mode: connect Gemini for a written morning brief.",
            "points": ["Every step of the run is listed with its outcome."], "watch": []}


# Scenario Studio offline: keyword rules stand in for Gemini, so local runs show a plausible, clearly labelled proposal.
_SCENARIO_RULES = [
    ("oil|crude|opec", "crisis_2008", [("energy", 30, "Oil and gas producers earn more when oil is dear."),
                                       ("consumer_cyclical", -15, "Fuel costs squeeze spending on everything else."),
                                       ("us_equity", -8, "Higher costs weigh on most companies.")]),
    ("recession|downturn|depression|unemployment", "crisis_2008", [
        ("us_equity", -25, "Earnings fall in a recession."), ("intl_equity", -20, "Recessions spread abroad."),
        ("bonds", 4, "Investors move to high-grade bonds."), ("financial_services", -30, "Loan losses rise.")]),
    (r"\bai\b|artificial intelligence|tech", "rates_2022", [
        ("technology", -40, "The companies behind AI reprice."), ("communication_services", -20, "AI platforms fall too."),
        ("us_equity", -8, "The rest of the market follows a little.")]),
    (r"(cut|lower|zero|fall)\w*.*\brates?\b|\brates?\b.*(cut|zero|fall)", "none", [
        ("bonds", 6, "Bond prices rise when yields fall."), ("us_equity", 5, "Cheaper money lifts valuations."),
        ("cash", -1, "Cash earns less.")]),
    (r"(rise|hike|up|climb|jump)\w*.*\brates?\b|\brates?\b.*(rise|hike|up|climb)|inflation", "rates_2022", [
        ("bonds", -8, "Bond prices fall when yields rise."), ("us_equity", -10, "Higher rates lower valuations."),
        ("realestate", -15, "Property is financed with debt.")]),
    ("dollar", "none", [("intl_equity", 8, "A weaker dollar lifts foreign assets in dollar terms.")]),
    ("pandemic|virus|lockdown|shutdown", "pandemic_2020", [
        ("us_equity", -20, "A sudden shutdown hits earnings."), ("intl_equity", -20, "Shutdowns are global."),
        ("energy", -35, "Travel and demand for fuel collapse.")]),
]
_OUT_OF_SCOPE = re.compile(r"\b(poem|story|song|joke|approve|approved)\b|\b(buy|sell)\s+\d|system:", re.I)


def _scenario_text(prompt: str) -> str:
    return prompt.split("<scenario>")[-1].split("</scenario>")[0].strip()


def _scenario_context(prompt: str) -> dict:
    return {"text": "Offline mode: no web search was run, so there is no current context.", "sources": []}


def _scenario_proposal(prompt: str) -> dict:
    text = _scenario_text(prompt)
    if _OUT_OF_SCOPE.search(text):
        return {"in_scope": False, "refusal": "Offline mode: Scenario Studio models market scenarios, such as a rate "
                                             "rise or an oil shock; it cannot help with this request."}
    shocks: dict[str, tuple[float, str]] = {}
    analogue = "none"
    for pattern, closest, rules in _SCENARIO_RULES:
        if re.search(pattern, text, re.I):
            analogue = closest if analogue == "none" else analogue
            for factor, pct, reason in rules:
                if factor not in shocks or abs(pct) > abs(shocks[factor][0]):
                    shocks[factor] = (pct, f"Offline rule: {reason}")
    if not shocks:
        shocks = {"us_equity": (-10.0, "Offline rule: a broad market fall."),
                  "bonds": (2.0, "Offline rule: high-grade bonds hold up.")}
    return {"in_scope": True, "title": f"Offline mode: {text}"[:120], "horizon_months": 12,
            "shocks": [{"factor": f, "pct": pct, "reason": reason} for f, (pct, reason) in shocks.items()],
            "analogue": analogue,
            "analogue_reason": "Offline rule: the closest replay by keyword." if analogue != "none" else "",
            "assumptions": ["Offline mode: keyword rules stand in for Gemini; connect Gemini for shocks grounded in "
                            "today's news."]}


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
        "aml_case_review": _case,
        "ops_brief": _brief,
        "scenario_context": _scenario_context, "scenario_proposal": _scenario_proposal,
        "scenario_narrative": _narrative,
    }, model="offline")
