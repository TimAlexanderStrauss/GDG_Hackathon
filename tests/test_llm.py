"""shared.llm: one env switch picks Gemini or an OpenAI-compatible endpoint (UniGPT). Offline: litellm is mocked."""
from types import SimpleNamespace

from shared import llm  # first: it keeps the litellm import offline

import litellm  # noqa: E402
from google.adk.models import Gemini  # noqa: E402
from google.adk.models.lite_llm import LiteLlm  # noqa: E402
from pydantic import BaseModel  # noqa: E402


class V(BaseModel):
    injection: bool


def test_agent_model_switch(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "gemini-3.8-flash")
    assert isinstance(llm.agent_model(), Gemini)
    monkeypatch.setenv("LLM_SMALL_MODEL", "openai/DeepSeek-V4-Flash")
    monkeypatch.setenv("UNIGPT_BASE_URL", "https://llm.example.org/v1")
    monkeypatch.setenv("UNIGPT_API_KEY", "k")
    m = llm.agent_model(small=True)
    assert isinstance(m, LiteLlm) and m.model == "openai/DeepSeek-V4-Flash"


def test_structured_openai_parses_or_returns_none(monkeypatch):
    monkeypatch.setenv("LLM_SMALL_MODEL", "openai/DeepSeek-V4-Flash")
    monkeypatch.setenv("UNIGPT_BASE_URL", "https://llm.example.org/v1")
    monkeypatch.setenv("UNIGPT_API_KEY", "k")
    sent, answer = {}, ['{"injection": true}']

    def fake(**kw):
        sent.update(kw)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=answer[0]))])
    monkeypatch.setattr(litellm, "completion", fake)
    assert llm.structured("sys", "<post>x</post>", V) == V(injection=True)
    assert sent["api_base"] == "https://llm.example.org/v1" and sent["response_format"]["type"] == "json_schema"
    answer[0] = "not json"
    assert llm.structured("sys", "x", V) is None  # the guard treats None as blocked (fail closed)


def test_think_false_turns_off_reasoning(monkeypatch):
    monkeypatch.setenv("UNIGPT_BASE_URL", "https://llm.example.org/v1")
    monkeypatch.setenv("UNIGPT_API_KEY", "k")
    off = {"chat_template_kwargs": {"enable_thinking": False}}
    assert llm._openai_args(think=False)["extra_body"] == off and "extra_body" not in llm._openai_args()
    monkeypatch.setenv("LLM_SMALL_MODEL", "openai/DeepSeek-V4-Flash")
    sent = {}
    monkeypatch.setattr(litellm, "completion", lambda **kw: sent.update(kw) or SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"injection": false}'))]))
    llm.structured("s", "u", V, think=False)
    assert sent["extra_body"] == off
