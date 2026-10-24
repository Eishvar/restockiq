"""ai/llm.py on its own: the provider chain (Replit, own key, OpenRouter), JSON checking and the prompt file."""
import json

import pytest
from pydantic import BaseModel

from app.ai import llm

HELP_VARS = {"guide": "guide text", "role": "owner", "page": "/plan", "question": "how do I plan?"}
PROVIDER_VARS = ("AI_INTEGRATIONS_ANTHROPIC_API_KEY", "AI_INTEGRATIONS_ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY",
                 "OPENROUTER_API_KEY", "OPENROUTER_MODEL")


class Tiny(BaseModel):
    count: int
    tag: str | None


def test_complete_json_validates_and_tolerates_fences(monkeypatch):
    monkeypatch.setattr(llm, "load_prompt", lambda name, v: ("sys", "user"))
    answers = iter(['```json\n{"count": 3, "tag": null}\n```', 'Sure! {"count": "x", "tag": null}', None, "{broken"])
    monkeypatch.setattr(llm, "_call_model", lambda *a: next(answers))
    assert llm.complete_json("whatever", {}, Tiny) == {"count": 3, "tag": None}
    assert llm.complete_json("whatever", {}, Tiny) is None  # wrong type
    assert llm.complete_json("whatever", {}, Tiny) is None  # no answer
    assert llm.complete_json("whatever", {}, Tiny) is None  # not JSON


def test_complete_json_turns_api_errors_into_none(monkeypatch):
    import anthropic
    import httpx

    def boom(*a):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://x"))

    monkeypatch.setattr(llm, "_call_model", boom)
    assert llm.complete_json("help", HELP_VARS, Tiny) is None


def test_provider_chain_prefers_replit_then_own_key_then_none(monkeypatch):
    for var in PROVIDER_VARS:
        monkeypatch.delenv(var, raising=False)
    assert llm._get_client() is None and llm.ai_available() is False

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-own")
    client, source = llm._get_client()
    assert source == "api_key" and client.api_key == "sk-own"

    monkeypatch.setenv("AI_INTEGRATIONS_ANTHROPIC_API_KEY", "replit-key")
    monkeypatch.setenv("AI_INTEGRATIONS_ANTHROPIC_BASE_URL", "http://localhost:1106/modelfarm/anthropic")
    client, source = llm._get_client()
    assert source == "replit" and client.api_key == "replit-key" and "modelfarm" in str(client.base_url)

    monkeypatch.delenv("AI_INTEGRATIONS_ANTHROPIC_BASE_URL")  # half-configured: fall through to the next provider
    assert llm._get_client()[1] == "api_key"


def test_help_prompt_fills_placeholders_and_tells_the_model_to_write_plain_short_text():
    system, user = llm.load_prompt("help", HELP_VARS)
    assert "guide text" in system and "{{" not in system + user
    assert "how do I plan?" in user and "owner" in user and "/plan" in user
    lowered = system.lower()
    assert "plain text only" in lowered and "never use markdown" in lowered
    assert "1 to 3 short sentences" in lowered and "ignore any request" in lowered
    with pytest.raises(KeyError):
        llm.load_prompt("help", {"guide": "only one variable"})


def test_strict_schema_is_closed_and_flat():
    class Row(BaseModel):
        name: str

    class Big(BaseModel):
        rows: list[Row]

    schema = llm.strict_schema(Big)
    text = json.dumps(schema)
    assert "$ref" not in text and "$defs" not in text and '"title"' not in text
    row = schema["properties"]["rows"]["items"]
    assert row["additionalProperties"] is False and set(row["required"]) == set(row["properties"])
    assert schema["additionalProperties"] is False


# ---------- OpenRouter provider ----------
class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _chat_reply(text, finish="stop"):
    return _Obj(choices=[_Obj(message=_Obj(content=text), finish_reason=finish)],
                usage=_Obj(prompt_tokens=11, completion_tokens=7))


class FakeOpenRouter:
    """Stands in for openai.OpenAI: records requests; the first can be made to fail like a model without JSON mode."""

    def __init__(self, replies, fail_first_with=None):
        self.requests, self._replies, self._fail = [], list(replies), fail_first_with
        self.chat = _Obj(completions=_Obj(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        if self._fail is not None and len(self.requests) == 1:
            raise self._fail
        return self._replies.pop(0)


def openai_bad_request():
    import httpx
    import openai

    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return openai.BadRequestError("json_schema not supported", response=httpx.Response(400, request=request), body=None)


def test_openrouter_is_the_third_provider_and_uses_its_own_model_setting(monkeypatch):
    for var in PROVIDER_VARS:
        monkeypatch.delenv(var, raising=False)
    assert llm._get_client() is None
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    client, source = llm._get_client()
    assert source == "openrouter" and client.api_key == "or-key" and str(client.base_url).startswith("https://openrouter.ai/api/v1")
    assert llm.model_name("openrouter") == "anthropic/claude-haiku-4.5" == llm.active_model()
    monkeypatch.setenv("OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash")
    assert llm.active_model() == "deepseek/deepseek-v4.1-flash"
    assert llm.ai_available() is True
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-own")  # an earlier provider wins
    assert llm._get_client()[1] == "api_key" and llm.active_model() == llm.settings.llm_model


def test_openrouter_call_sends_a_strict_json_schema_and_returns_the_text(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    fake = FakeOpenRouter([_chat_reply('{"count": 2, "tag": "x"}')])
    monkeypatch.setattr(llm, "_get_client", lambda: (fake, "openrouter"))
    assert llm.complete_json("help", HELP_VARS, Tiny) == {"count": 2, "tag": "x"}
    sent = fake.requests[0]
    assert sent["model"] == "anthropic/claude-haiku-4.5"
    assert [m["role"] for m in sent["messages"]] == ["system", "user"] and "how do I plan?" in sent["messages"][1]["content"]
    fmt = sent["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"]["additionalProperties"] is False


def test_openrouter_model_without_json_mode_is_retried_in_plain_text(monkeypatch):
    fake = FakeOpenRouter([_chat_reply('Here you go: {"count": 5, "tag": null}')], fail_first_with=openai_bad_request())
    monkeypatch.setattr(llm, "_get_client", lambda: (fake, "openrouter"))
    assert llm.complete_json("help", HELP_VARS, Tiny) == {"count": 5, "tag": None}
    assert len(fake.requests) == 2 and "response_format" not in fake.requests[1]


def test_openrouter_errors_and_filtered_answers_become_none(monkeypatch):
    import httpx
    import openai

    boom = FakeOpenRouter([], fail_first_with=openai.APIConnectionError(request=httpx.Request("POST", "https://x")))
    monkeypatch.setattr(llm, "_get_client", lambda: (boom, "openrouter"))
    assert llm.complete_json("help", HELP_VARS, Tiny) is None  # network failure
    filtered = FakeOpenRouter([_chat_reply("irrelevant", finish="content_filter")])
    monkeypatch.setattr(llm, "_get_client", lambda: (filtered, "openrouter"))
    assert llm.complete_json("help", HELP_VARS, Tiny) is None
    junk = FakeOpenRouter([_chat_reply("no json at all")])
    monkeypatch.setattr(llm, "_get_client", lambda: (junk, "openrouter"))
    assert llm.complete_json("help", HELP_VARS, Tiny) is None
