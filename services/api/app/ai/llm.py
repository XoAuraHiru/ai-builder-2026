"""One narrow door to generative AI. Every call returns parsed output plus the facts the decision log needs."""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from app.config import Settings, get_settings

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class Attachment:
    data: bytes
    mime_type: str


@dataclass(frozen=True)
class LLMResult:
    parsed: Any
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_usd: float


@dataclass(frozen=True)
class GroundedResult:
    """Prose grounded with Google Search, the web pages it rests on, and what the call cost."""
    text: str
    sources: list[dict]  # [{"title": str, "uri": str}]
    queries: int         # web searches Gemini ran; each is charged
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_usd: float
    search_html: str = ""  # Google Search suggestions as Google renders them; its terms require showing them


MAX_SOURCES = 6


class LLMError(Exception):
    pass


class LLM(Protocol):
    def generate_json(self, *, purpose: str, prompt: str, schema: type[T],
                      attachments: list[Attachment] | None = None, pro: bool = False) -> LLMResult: ...

    def generate_grounded(self, *, purpose: str, prompt: str) -> GroundedResult: ...


def price_usd(settings: Settings, model: str, tokens_in: int, tokens_out: int) -> float:
    if model == settings.gemini_pro_model:
        rate_in, rate_out = settings.gemini_pro_input_usd_per_m, settings.gemini_pro_output_usd_per_m
    else:
        rate_in, rate_out = settings.gemini_flash_input_usd_per_m, settings.gemini_flash_output_usd_per_m
    return round((tokens_in * rate_in + tokens_out * rate_out) / 1_000_000, 6)


def retry_options():
    """Back off and retry on rate limits and transient errors; new projects start with low Gemini quotas."""
    from google.genai import types

    return types.HttpRetryOptions(attempts=4, initial_delay=2.0, max_delay=20.0,
                                  http_status_codes=[429, 500, 502, 503, 504])


class FakeLLM:
    """Deterministic stand-in for tests and offline development. Responses are keyed by purpose."""

    def __init__(self, responses: dict[str, dict | Callable[[str], dict]] | None = None, model: str = "fake-llm"):
        self.responses = dict(responses or {})
        self.model = model
        self.calls: list[dict] = []

    def generate_json(self, *, purpose, prompt, schema, attachments=None, pro=False) -> LLMResult:
        self.calls.append({"purpose": purpose, "prompt": prompt, "attachments": list(attachments or []), "pro": pro})
        if purpose not in self.responses:
            raise LLMError(f"FakeLLM has no response for purpose {purpose!r}")
        raw = self.responses[purpose]
        data = raw(prompt) if callable(raw) else raw
        return LLMResult(parsed=schema.model_validate(data), model=self.model, tokens_in=len(prompt) // 4,
                         tokens_out=50, latency_ms=1, cost_usd=0.0)

    def generate_grounded(self, *, purpose, prompt) -> GroundedResult:
        """responses[purpose] is {"text", "sources"}, or a callable of the prompt that returns one."""
        self.calls.append({"purpose": purpose, "prompt": prompt, "attachments": [], "pro": False, "grounded": True})
        if purpose not in self.responses:
            raise LLMError(f"FakeLLM has no response for purpose {purpose!r}")
        raw = self.responses[purpose]
        data = raw(prompt) if callable(raw) else raw
        sources = [dict(s) for s in data.get("sources", [])][:MAX_SOURCES]
        return GroundedResult(text=data["text"], sources=sources, queries=len(sources), model=self.model,
                              tokens_in=len(prompt) // 4, tokens_out=50, latency_ms=1, cost_usd=0.0,
                              search_html=data.get("search_html", ""))


class GeminiLLM:
    """Gemini on Vertex AI through google-genai. Imported lazily so cold starts stay light."""

    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        if client is None:
            from google import genai
            from google.genai import types

            client = genai.Client(enterprise=True, project=settings.gcp_project, location=settings.gemini_location,
                                  http_options=types.HttpOptions(retry_options=retry_options()))
        self._client = client

    def generate_json(self, *, purpose, prompt, schema, attachments=None, pro=False) -> LLMResult:
        from google.genai import types

        model = self.settings.gemini_pro_model if pro else self.settings.gemini_flash_model
        contents: list = [types.Part.from_bytes(data=a.data, mime_type=a.mime_type) for a in attachments or []]
        contents.append(prompt)
        config_args: dict = {"response_mime_type": "application/json", "response_schema": schema}
        # Thinking level is Gemini 3's quality, latency and cost dial. LOW suits grounded writing from given facts:
        # at its default, a Pro proposal took about 95 s and $0.11; at LOW it is far quicker and cheaper.
        config_args["thinking_config"] = types.ThinkingConfig(thinking_level="LOW")
        started = time.perf_counter()
        try:
            resp = self._client.models.generate_content(
                model=model, contents=contents, config=types.GenerateContentConfig(**config_args))
        except Exception as e:  # the SDK raises several error types; callers handle one
            raise LLMError(f"{purpose}: Gemini call failed: {e}") from e
        latency_ms = int((time.perf_counter() - started) * 1000)
        try:
            parsed = resp.parsed if isinstance(resp.parsed, schema) else schema.model_validate_json(resp.text or "{}")
        except ValueError as e:
            raise LLMError(f"{purpose}: Gemini returned output that does not match the schema: {e}") from e
        usage = resp.usage_metadata
        tokens_in = (usage.prompt_token_count or 0) if usage else 0
        tokens_out = ((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)) if usage else 0
        return LLMResult(parsed=parsed, model=model, tokens_in=tokens_in, tokens_out=tokens_out,
                         latency_ms=latency_ms, cost_usd=price_usd(self.settings, model, tokens_in, tokens_out))

    def generate_grounded(self, *, purpose, prompt) -> GroundedResult:
        """Flash with the Google Search tool: prose about the present, with the pages it rests on. An empty answer is
        returned, not raised, because it was still charged and the caller records every call."""
        from google.genai import types

        model = self.settings.gemini_flash_model
        config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())],
                                             thinking_config=types.ThinkingConfig(thinking_level="LOW"))
        started = time.perf_counter()
        try:
            resp = self._client.models.generate_content(model=model, contents=[prompt], config=config)
            text = resp.text
        except Exception as e:  # the SDK raises several error types; callers handle one
            raise LLMError(f"{purpose}: Gemini grounded call failed: {e}") from e
        latency_ms = int((time.perf_counter() - started) * 1000)
        candidates = getattr(resp, "candidates", None) or []
        metadata = getattr(candidates[0], "grounding_metadata", None) if candidates else None
        sources: list[dict] = []
        for chunk in getattr(metadata, "grounding_chunks", None) or []:
            web = getattr(chunk, "web", None)
            uri = getattr(web, "uri", None) if web is not None else None
            if uri and all(s["uri"] != uri for s in sources):
                sources.append({"title": getattr(web, "title", None) or uri, "uri": uri})
            if len(sources) == MAX_SOURCES:
                break
        queries = len(getattr(metadata, "web_search_queries", None) or [])
        entry = getattr(metadata, "search_entry_point", None)
        usage = resp.usage_metadata
        tokens_in = (usage.prompt_token_count or 0) if usage else 0
        tokens_out = ((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)) if usage else 0
        cost = price_usd(self.settings, model, tokens_in, tokens_out) + queries * self.settings.search_usd_per_query
        return GroundedResult(text=(text or "").strip(), sources=sources, queries=queries, model=model,
                              tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=latency_ms,
                              cost_usd=round(cost, 6), search_html=getattr(entry, "rendered_content", None) or "")


_gemini: GeminiLLM | None = None


def get_llm() -> LLM:
    """FastAPI dependency. Tests override it with a FakeLLM."""
    global _gemini
    settings = get_settings()
    if settings.llm_provider == "gemini":
        if _gemini is None:
            _gemini = GeminiLLM(settings)
        return _gemini
    from app.ai.offline import offline_llm

    return offline_llm()
