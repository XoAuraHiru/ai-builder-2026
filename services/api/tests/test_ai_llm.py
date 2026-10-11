from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.ai.llm import Attachment, FakeLLM, GeminiLLM, LLMError, get_llm, price_usd
from app.config import Settings


class Answer(BaseModel):
    label: str
    score: float


def test_fake_llm_validates_against_schema_and_records_calls():
    llm = FakeLLM({"classify": {"label": "ok", "score": 0.9}})
    result = llm.generate_json(purpose="classify", prompt="hello", schema=Answer)
    assert result.parsed == Answer(label="ok", score=0.9)
    assert llm.calls[0]["purpose"] == "classify" and llm.calls[0]["prompt"] == "hello"


def test_fake_llm_responder_can_read_the_prompt():
    llm = FakeLLM({"classify": lambda prompt: {"label": prompt.upper(), "score": 1.0}})
    assert llm.generate_json(purpose="classify", prompt="abc", schema=Answer).parsed.label == "ABC"


def test_fake_llm_unknown_purpose_raises():
    with pytest.raises(LLMError):
        FakeLLM({}).generate_json(purpose="nope", prompt="x", schema=Answer)


def test_price_usd_uses_flash_and_pro_rates():
    s = Settings(_env_file=None)
    assert price_usd(s, s.gemini_flash_model, 1_000_000, 0) == pytest.approx(0.75)
    assert price_usd(s, s.gemini_flash_model, 0, 1_000_000) == pytest.approx(3.75)
    assert price_usd(s, s.gemini_pro_model, 1_000_000, 1_000_000) == pytest.approx(14.0)


class FakeModels:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.kwargs = response, error, None

    def generate_content(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def test_gemini_llm_builds_structured_request_and_reads_usage():
    s = Settings(_env_file=None, gcp_project="p")
    usage = SimpleNamespace(prompt_token_count=1000, candidates_token_count=200, thoughts_token_count=100)
    models = FakeModels(SimpleNamespace(parsed=Answer(label="x", score=0.5), text="", usage_metadata=usage))
    llm = GeminiLLM(s, client=SimpleNamespace(models=models))
    result = llm.generate_json(purpose="classify", prompt="hi", schema=Answer,
                               attachments=[Attachment(b"\x89PNG", "image/png")])
    assert models.kwargs["model"] == "gemini-3.8-flash"
    config = models.kwargs["config"]
    assert config.response_mime_type == "application/json" and config.response_schema is Answer
    assert str(config.thinking_config.thinking_level).upper().endswith("LOW")
    assert len(models.kwargs["contents"]) == 2 and models.kwargs["contents"][-1] == "hi"
    assert result.parsed.label == "x" and result.tokens_in == 1000 and result.tokens_out == 300
    assert result.cost_usd == pytest.approx((1000 * 0.75 + 300 * 3.75) / 1_000_000)


def test_gemini_llm_parses_text_when_parsed_is_missing_and_uses_pro_without_thinking_config():
    s = Settings(_env_file=None, gcp_project="p")
    models = FakeModels(SimpleNamespace(parsed=None, text='{"label": "y", "score": 0.1}', usage_metadata=None))
    result = GeminiLLM(s, client=SimpleNamespace(models=models)).generate_json(
        purpose="c", prompt="p", schema=Answer, pro=True)
    assert models.kwargs["model"] == "gemini-3.1-pro-preview"
    assert models.kwargs["config"].thinking_config is None
    assert result.parsed.label == "y" and result.tokens_in == 0


def test_gemini_llm_wraps_errors():
    s = Settings(_env_file=None, gcp_project="p")
    llm = GeminiLLM(s, client=SimpleNamespace(models=FakeModels(error=RuntimeError("quota"))))
    with pytest.raises(LLMError, match="quota"):
        llm.generate_json(purpose="c", prompt="p", schema=Answer)


def test_get_llm_is_offline_fake_by_default():
    assert isinstance(get_llm(), FakeLLM)
