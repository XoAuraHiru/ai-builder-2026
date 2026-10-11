import json
import subprocess
import sys
from typing import AsyncGenerator

import pytest
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from app.agents.advisor import get_agent_model
from app.ai.llm import FakeLLM, get_llm
from app.seed.funds import seed_funds

STAFF = {"X-Dev-User": "daniel@atrium.demo"}


class ScriptedLlm(BaseLlm):
    model: str = "scripted"
    responses: list[LlmResponse] = []
    requests: list[LlmRequest] = []

    async def generate_content_async(self, llm_request: LlmRequest,
                                     stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        self.requests.append(llm_request)
        yield self.responses.pop(0)


def call(name, **args):
    return LlmResponse(content=types.Content(role="model", parts=[
        types.Part(function_call=types.FunctionCall(name=name, args=args))]))


def say(text):
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


def tool_results(llm):
    out = []
    for request in llm.requests:
        for content in request.contents:
            for part in content.parts or []:
                if part.function_response and part.function_response.response not in out:
                    out.append(part.function_response.response)
    return out


@pytest.fixture()
def agent_client(client, db, people):
    seed_funds(db)
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({"compliance_review": {"findings": []}})
    return client


def test_draft_reply_uses_tools_and_rechecks_compliance(agent_client, make_lead):
    lead = make_lead(email="x@mailinator.com")
    scripted = ScriptedLlm(responses=[
        call("get_lead_profile"),
        call("check_draft_compliance", text="Hi Ava, returns are guaranteed."),
        say(json.dumps({"subject": "Your Atrium enquiry", "body": "Hi Ava, returns are guaranteed."}))])
    agent_client.app.dependency_overrides[get_agent_model] = lambda: scripted
    r = agent_client.post(f"/leads/{lead.id}/draft-reply", headers=STAFF)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["subject"] == "Your Atrium enquiry" and body["compliance"]["ok"] is False
    results = tool_results(scripted)
    assert results[0]["full_name"] == "Ava Thompson" and results[1]["ok"] is False


def test_ask_routes_to_the_trust_specialist(agent_client, db, make_lead):
    from app.services.trust import apply_trust

    lead = make_lead(email="x@mailinator.com")
    apply_trust(db, lead)
    db.commit()
    scripted = ScriptedLlm(responses=[
        call("trust_and_fraud", request="Why was this lead flagged?"),
        call("get_trust_report"),
        say("Flagged because the email uses a disposable domain (T01)."),
        say("This lead was flagged because its email is a disposable mailbox.")])
    agent_client.app.dependency_overrides[get_agent_model] = lambda: scripted
    r = agent_client.post(f"/leads/{lead.id}/ask", json={"question": "Why was this lead flagged?"}, headers=STAFF)
    assert r.status_code == 200, r.text
    assert "disposable" in r.json()["answer"]
    assert any(isinstance(res, dict) and res.get("signals") and res["signals"][0]["code"] == "T01"
               for res in tool_results(scripted))


def test_agent_endpoints_are_staff_only(agent_client, make_lead):
    lead = make_lead()
    r = agent_client.post(f"/leads/{lead.id}/draft-reply", headers={"X-Dev-User": "priya@atrium.demo"})
    assert r.status_code == 403


def test_cold_start_does_not_import_ai_sdks():
    code = ("import sys, app.main; "
            "print([m for m in ('google.adk', 'google.genai', 'google.cloud.documentai', 'google.cloud.bigquery') "
            "if m in sys.modules])")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]"
