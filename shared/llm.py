"""One switch for every LLM call. LLM_MODEL / LLM_SMALL_MODEL in .env:
- "gemini-..."      -> Google Gemini API (GOOGLE_API_KEY)
- "openai/<model>"  -> an OpenAI-compatible endpoint, e.g. UniGPT (UNIGPT_BASE_URL, UNIGPT_API_KEY), via LiteLLM

Env is read at call time: callers load .env before they build agents or call structured().
"""
import os
from functools import cache

from pydantic import BaseModel

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")  # else importing litellm downloads a price list from GitHub


def model_name(small: bool = False) -> str:
    if small:
        return os.getenv("LLM_SMALL_MODEL", "gemini-3.5-flash-lite")
    return os.getenv("LLM_MODEL") or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


def _openai_args(think: bool = True) -> dict:
    args = {"api_base": os.environ["UNIGPT_BASE_URL"], "api_key": os.environ["UNIGPT_API_KEY"], "num_retries": 3}
    if not think:  # reasoning models (DeepSeek-V4, Qwen3) think ~90 % of their output: 3 min instead of 9 s for extraction
        args["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    return args


def agent_model(small: bool = False, think: bool = True):
    """The model object for an ADK LlmAgent. think=False: no reasoning tokens (openai/ models; simple tasks)."""
    name = model_name(small)
    if name.startswith("openai/"):
        from google.adk.models.lite_llm import LiteLlm
        return LiteLlm(model=name, **_openai_args(think))
    from google.adk.models import Gemini
    from google.genai import types
    return Gemini(model=name, retry_options=types.HttpRetryOptions(attempts=3))


@cache
def _gemini():
    from google import genai
    return genai.Client(http_options=genai.types.HttpOptions(retry_options=genai.types.HttpRetryOptions(attempts=3)))


def structured[T: BaseModel](system: str, user: str, schema: type[T], small: bool = True, think: bool = True) -> T | None:
    """One call with a JSON schema answer (small model by default). None if the answer does not fit the schema."""
    name = model_name(small=small)
    if name.startswith("openai/"):
        import litellm
        from google.adk.models.lite_llm import _to_litellm_response_format
        r = litellm.completion(model=name, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                               response_format=_to_litellm_response_format(schema, name), **_openai_args(think))
        try:
            return schema.model_validate_json(r.choices[0].message.content or "")
        except ValueError:
            return None
    r = _gemini().models.generate_content(model=name, contents=user, config={
        "system_instruction": system, "response_mime_type": "application/json", "response_schema": schema})
    return r.parsed
