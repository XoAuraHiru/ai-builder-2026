"""Advisor-facing agents: Lead Intelligence drafts and plans, Trust & Fraud explains risk, a router picks between them.

Tools read a snapshot taken before the agent runs, so nothing touches the database from inside the agent loop.
The final draft is re-checked on the server, so a model that skips its compliance tool cannot ship a bad draft.
"""
import asyncio
import json
import logging
import re
import time

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.decisions import record_decision
from app.ai.llm import LLM, LLMResult, price_usd
from app.config import get_settings
from app.models import Fund, Lead
from app.services.compliance import check_compliance

log = logging.getLogger(__name__)

LEAD_INTEL = """You are Atrium's Lead Intelligence agent helping an advisor.
Always call get_lead_profile first. Use list_house_funds when you mention funds.
To draft a reply: write a warm, specific first email in plain English (under 180 words), mention at most two suitable
house funds by name, never promise returns, and end with a clear next step. Call check_draft_compliance on your draft
and revise until it returns ok. Reply with JSON only: {"subject": "...", "body": "..."}."""
TRUST = """You are Atrium's Trust & Fraud agent. Explain a lead's Trust Score to an advisor using get_trust_report.
Cite signal codes and evidence. Suggest proportionate next steps (verify, call, hold). Never accuse; describe risk."""
ROUTER = """You are the advisor's concierge. Route questions about fit, goals, funds or messages to lead_intelligence,
and questions about risk, fraud, identity or trust to trust_and_fraud. Answer the advisor concisely with their result."""


class DraftReply(BaseModel):
    subject: str = Field(max_length=200)
    body: str = Field(max_length=4000)


def _offline_agent_llm():
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types

    class OfflineAgentLlm(BaseLlm):
        """Lets the agent endpoints work without Gemini credentials (local development)."""

        model: str = "offline-agent"

        async def generate_content_async(self, llm_request, stream: bool = False):
            wants_json = "JSON only" in str(llm_request.config.system_instruction or "")
            text = (json.dumps({"subject": "Following up on your Atrium enquiry",
                                "body": "Offline draft: connect Gemini to generate a personalised reply."})
                    if wants_json else "Offline mode: connect Gemini to get answers.")
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))

    return OfflineAgentLlm()


def get_agent_model():
    """FastAPI dependency: the Gemini model id (ADK reads the Vertex AI settings from the environment) or offline."""
    settings = get_settings()
    if settings.llm_provider == "gemini":
        from google.adk.models import Gemini

        from app.ai.llm import retry_options

        return Gemini(model=settings.gemini_flash_model, retry_options=retry_options())
    return _offline_agent_llm()


class AgentUnavailable(Exception):
    """The agent could not finish (rate limit, timeout, model error). Callers answer 503, never 500."""


def _snapshot(db: Session, lead: Lead) -> dict:
    funds = db.scalars(select(Fund).order_by(Fund.risk_band, Fund.code)).all()
    return {
        "profile": {"full_name": lead.full_name, "source": lead.source, "country": lead.country, "goals": lead.goals,
                    "horizon_years": lead.horizon_years, "investable_usd": str(lead.investable_usd),
                    "monthly_usd": str(lead.monthly_usd), "source_of_funds": lead.source_of_funds,
                    "stage": lead.stage, "enrichment": lead.enrichment, "lead_score": lead.lead_score,
                    "lead_score_factors": lead.lead_score_factors, "trust_score": lead.trust_score,
                    "trust_band": lead.trust_band},
        "trust": {"score": lead.trust_score, "band": lead.trust_band, "signals": lead.trust_signals or []},
        "funds": [{"code": f.code, "name": f.name, "risk_band": f.risk_band, "objective": f.objective,
                   "who_for": f.who_for, "fee_bps": f.fee_bps} for f in funds],
    }


def build_agents(snapshot: dict, llm: LLM, model):
    from google.adk.agents import Agent
    from google.adk.tools.agent_tool import AgentTool
    from google.genai import types

    # Flash's quality and latency dial: LOW keeps the router-specialist round trip quick and cheap.
    fast = types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level="LOW"))

    def get_lead_profile() -> dict:
        """Return the lead's form answers, AI enrichment, Lead Score and Trust Score."""
        return snapshot["profile"]

    def get_trust_report() -> dict:
        """Return the lead's Trust Score, band and every signal with its evidence."""
        return snapshot["trust"]

    def list_house_funds() -> dict:
        """Return Atrium's house funds with code, name, risk band, objective, who each suits and fee in basis points."""
        return {"funds": snapshot["funds"]}

    def check_draft_compliance(text: str) -> dict:
        """Check a draft client message for marketing-rule problems. Returns ok and a list of findings."""
        return check_compliance(text, llm).model_dump()

    lead_intel = Agent(name="lead_intelligence", model=model,
                       description="Plans next steps and drafts replies for a lead.",
                       instruction=LEAD_INTEL, tools=[get_lead_profile, list_house_funds, check_draft_compliance],
                       generate_content_config=fast)
    trust = Agent(name="trust_and_fraud", model=model, description="Explains a lead's Trust Score and fraud signals.",
                  instruction=TRUST, tools=[get_trust_report, get_lead_profile], generate_content_config=fast)
    router = Agent(name="advisor_concierge", model=model, instruction=ROUTER,
                   tools=[AgentTool(agent=lead_intel), AgentTool(agent=trust)], generate_content_config=fast)
    return router, lead_intel


async def _run(agent, message: str) -> tuple[str, int, int]:
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    sessions = InMemorySessionService()
    runner = Runner(app_name="atrium", agent=agent, session_service=sessions)
    session = await sessions.create_session(app_name="atrium", user_id="advisor")
    final, tokens_in, tokens_out = "", 0, 0
    async for event in runner.run_async(user_id="advisor", session_id=session.id,
                                        new_message=types.Content(role="user", parts=[types.Part(text=message)])):
        usage = getattr(event, "usage_metadata", None)
        if usage:
            tokens_in += usage.prompt_token_count or 0
            tokens_out += (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
        if event.is_final_response() and event.content and event.content.parts:
            final = "".join(p.text or "" for p in event.content.parts)
    return final, tokens_in, tokens_out


def _run_agent(agent, message: str) -> tuple[str, int, int]:
    try:
        return asyncio.run(_run(agent, message))
    except Exception as e:  # ADK wraps model errors in several types; the advisor only needs "try again"
        log.warning("agent %s failed: %s", getattr(agent, "name", "?"), e)
        raise AgentUnavailable(str(e)) from e


def _model_name(model) -> str:
    return model if isinstance(model, str) else str(getattr(model, "model", "agent"))


def _record(db: Session, lead: Lead, purpose: str, model, output: dict, tokens_in: int, tokens_out: int,
            started: float, prompt: str) -> None:
    name = _model_name(model)
    result = LLMResult(parsed=output, model=name, tokens_in=tokens_in, tokens_out=tokens_out,
                       latency_ms=int((time.perf_counter() - started) * 1000),
                       cost_usd=price_usd(get_settings(), name, tokens_in, tokens_out))
    record_decision(db, agent="lead_intelligence" if purpose == "draft_reply" else "advisor_concierge",
                    purpose=purpose, result=result, subject_type="lead", subject_id=lead.id, input_text=prompt)


def _parse_draft(text: str) -> DraftReply:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    try:
        if match:
            return DraftReply.model_validate_json(match.group(0))
    except ValueError:
        pass
    return DraftReply(subject="Your Atrium enquiry", body=text.strip()[:4000])


def draft_reply(db: Session, lead: Lead, llm: LLM, model) -> dict:
    _, lead_intel = build_agents(_snapshot(db, lead), llm, model)
    prompt = f"Draft the first reply email to {lead.full_name}."
    started = time.perf_counter()
    text, tokens_in, tokens_out = _run_agent(lead_intel, prompt)
    draft = _parse_draft(text)
    compliance = check_compliance(f"{draft.subject}\n\n{draft.body}", llm, db=db, subject_id=lead.id)
    output = {**draft.model_dump(), "compliance": compliance.model_dump()}
    _record(db, lead, "draft_reply", model, output, tokens_in, tokens_out, started, prompt)
    return output


def ask_about_lead(db: Session, lead: Lead, question: str, llm: LLM, model) -> str:
    router, _ = build_agents(_snapshot(db, lead), llm, model)
    started = time.perf_counter()
    answer, tokens_in, tokens_out = _run_agent(router, question)
    _record(db, lead, "advisor_question", model, {"question": question, "answer": answer}, tokens_in, tokens_out,
            started, question)
    return answer
