"""Gemini grounded with Google Search: the request it builds, the sources it keeps, and what it costs."""
from types import SimpleNamespace

import pytest

from app.ai.llm import FakeLLM, GeminiLLM, GroundedResult, LLMError
from app.config import Settings


class FakeModels:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.kwargs = response, error, None

    def generate_content(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def web(uri, title):
    return SimpleNamespace(web=SimpleNamespace(uri=uri, title=title))


def response(chunks, queries, text="Rates are 4.25% today.", usage=None, rendered=None):
    entry = SimpleNamespace(rendered_content=rendered) if rendered is not None else None
    metadata = SimpleNamespace(grounding_chunks=chunks, web_search_queries=queries, search_entry_point=entry)
    return SimpleNamespace(text=text, candidates=[SimpleNamespace(grounding_metadata=metadata)],
                           usage_metadata=usage)


def test_grounded_call_searches_keeps_distinct_sources_and_charges_for_queries():
    s = Settings(_env_file=None, gcp_project="p")
    usage = SimpleNamespace(prompt_token_count=1000, candidates_token_count=200, thoughts_token_count=100)
    chunks = [web("https://example.test/fed", "Fed holds rates"), web("https://example.test/fed", "Fed holds rates")]
    models = FakeModels(response(chunks, ["fed funds rate", "oil price today"], usage=usage,
                                 rendered='<div class="chips">fed funds rate</div>'))
    result = GeminiLLM(s, client=SimpleNamespace(models=models)).generate_grounded(purpose="scenario_context",
                                                                                   prompt="the scenario")
    assert isinstance(result, GroundedResult)
    assert result.search_html == '<div class="chips">fed funds rate</div>'  # Google's terms: show the suggestions
    assert models.kwargs["model"] == "gemini-3.8-flash" and models.kwargs["contents"] == ["the scenario"]
    config = models.kwargs["config"]
    assert len(config.tools) == 1 and config.tools[0].google_search is not None
    assert str(config.thinking_config.thinking_level).upper().endswith("LOW")
    assert result.text == "Rates are 4.25% today."
    assert result.sources == [{"title": "Fed holds rates", "uri": "https://example.test/fed"}]
    assert result.queries == 2 and result.tokens_in == 1000 and result.tokens_out == 300
    assert result.cost_usd == pytest.approx((1000 * 0.75 + 300 * 3.75) / 1_000_000 + 2 * 0.014)
    assert result.model == "gemini-3.8-flash" and result.latency_ms >= 0


def test_grounded_call_keeps_at_most_six_web_sources_and_survives_no_search():
    s = Settings(_env_file=None, gcp_project="p", search_usd_per_query=0.02)
    chunks = [web(f"https://example.test/{i}", None if i == 0 else f"Story {i}") for i in range(8)]
    chunks.insert(1, SimpleNamespace(web=None))  # a chunk from another kind of grounding
    result = GeminiLLM(s, client=SimpleNamespace(models=FakeModels(response(chunks, ["q"])))).generate_grounded(
        purpose="c", prompt="p")
    assert [x["uri"] for x in result.sources] == [f"https://example.test/{i}" for i in range(6)]
    assert result.sources[0]["title"] == "https://example.test/0"  # no title: the address stands in
    assert result.cost_usd == pytest.approx(0.02) and result.tokens_in == 0

    bare = SimpleNamespace(text="From memory.", candidates=[SimpleNamespace(grounding_metadata=None)],
                           usage_metadata=None)
    plain = GeminiLLM(s, client=SimpleNamespace(models=FakeModels(bare))).generate_grounded(purpose="c", prompt="p")
    assert plain.sources == [] and plain.queries == 0 and plain.cost_usd == 0 and plain.search_html == ""


def test_grounded_call_errors_become_llm_errors_but_an_empty_answer_is_still_charged():
    s = Settings(_env_file=None, gcp_project="p")
    failing = GeminiLLM(s, client=SimpleNamespace(models=FakeModels(error=RuntimeError("search quota"))))
    with pytest.raises(LLMError, match="search quota"):
        failing.generate_grounded(purpose="scenario_context", prompt="p")
    empty = GeminiLLM(s, client=SimpleNamespace(models=FakeModels(response([], ["q"], text=None))))
    result = empty.generate_grounded(purpose="scenario_context", prompt="p")
    assert result.text == "" and result.queries == 1 and result.cost_usd == pytest.approx(0.014)


def test_fake_grounded_call_returns_its_script_and_records_the_call():
    sources = [{"title": "Oil", "uri": "https://example.test/oil"}]
    llm = FakeLLM({"scenario_context": {"text": "Oil is $80.", "sources": sources, "search_html": "<div>oil</div>"},
                   "echo": lambda prompt: {"text": prompt.upper(), "sources": []}})
    result = llm.generate_grounded(purpose="scenario_context", prompt="oil at 150")
    assert result.text == "Oil is $80." and result.sources == sources and result.cost_usd == 0
    assert result.search_html == "<div>oil</div>"
    assert llm.calls[-1]["purpose"] == "scenario_context" and llm.calls[-1]["prompt"] == "oil at 150"
    assert llm.generate_grounded(purpose="echo", prompt="abc").text == "ABC"
    with pytest.raises(LLMError):
        llm.generate_grounded(purpose="missing", prompt="x")
