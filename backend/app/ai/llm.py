"""The only door to the LLM. Everything else in the app calls complete_json().

Rules this module enforces:
- The LLM only reads messy human text and returns structured JSON. It never decides purchase quantities.
- Output is validated against a pydantic model; anything invalid is treated as "no answer" (None).
- If no model is reachable (no key, timeout, bad answer) callers get None and fall back to manual entry.

Provider chain (isolated in _get_client), first one that is configured wins:
  1. Replit-managed Anthropic integration   (Claude, no key of our own)
  2. our own ANTHROPIC_API_KEY              (Claude, direct)
  3. OPENROUTER_API_KEY                     (any model through OpenRouter; model from OPENROUTER_MODEL)
  4. none -> callers fall back to manual entry
"""
import json
import logging
import os
import re
from pathlib import Path

import anthropic
import openai
from pydantic import BaseModel

from app.config import settings

log = logging.getLogger("restockiq.ai")

PROMPTS_DIR = Path(__file__).parent / "prompts"
USER_MARKER = "---USER---"  # a prompt file is "system text", this marker line, then "user text"
TIMEOUT_SECONDS = 20
MAX_TOKENS = 4096

# JSON-schema keywords the structured-output endpoint does not take; pydantic still enforces them afterwards.
_UNSUPPORTED = {
    "title", "default", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "minLength", "maxLength", "minItems", "maxItems", "pattern", "format",
}


# ---------- provider chain ----------
OPENROUTER_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "anthropic/claude-haiku-4.5"  # an OpenRouter model id; override with OPENROUTER_MODEL


def _get_client() -> tuple[anthropic.Anthropic | openai.OpenAI, str] | None:
    """(client, source) for the first provider that is configured, else None.

    source is "replit", "api_key" or "openrouter". The first two are Anthropic clients, the last an OpenAI-style one.
    """
    key, base = os.getenv("AI_INTEGRATIONS_ANTHROPIC_API_KEY"), os.getenv("AI_INTEGRATIONS_ANTHROPIC_BASE_URL")
    if key and base:  # Replit AI Integrations: no key of our own to manage
        return anthropic.Anthropic(api_key=key, base_url=base, timeout=TIMEOUT_SECONDS, max_retries=1), "replit"
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:
        return anthropic.Anthropic(api_key=key, timeout=TIMEOUT_SECONDS, max_retries=1), "api_key"
    key = os.getenv("OPENROUTER_API_KEY")
    if key:
        client = openai.OpenAI(
            api_key=key, base_url=OPENROUTER_URL, timeout=TIMEOUT_SECONDS, max_retries=1,
            default_headers={"X-Title": "RestockIQ"},  # shows the app's name in OpenRouter's usage list
        )
        return client, "openrouter"
    return None


def ai_available() -> bool:
    """True if a provider is configured (it may still fail at call time)."""
    return _get_client() is not None


# ---------- prompts ----------
def load_prompt(name: str, variables: dict) -> tuple[str, str]:
    """Read prompts/<name>.md and fill {{variable}} placeholders. Returns (system, user)."""
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    system, _, user = text.partition(USER_MARKER)

    def fill(match: re.Match) -> str:
        value = variables[match.group(1)]  # a missing variable is a bug, so let it raise
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)

    return re.sub(r"\{\{(\w+)\}\}", fill, system).strip(), re.sub(r"\{\{(\w+)\}\}", fill, user).strip()


def strict_schema(model: type[BaseModel]) -> dict:
    """JSON schema for structured output: refs inlined, every object closed, every property required."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def fix(node):
        if isinstance(node, list):
            return [fix(v) for v in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            node = dict(defs[node["$ref"].split("/")[-1]])
        node = {k: fix(v) for k, v in node.items() if k not in _UNSUPPORTED}
        if node.get("type") == "object":
            node["additionalProperties"] = False
            node["required"] = list(node.setdefault("properties", {}))
        return node

    return fix(schema)


# ---------- the call ----------
def model_name(source: str) -> str:
    """The model id the given provider will be asked for."""
    return os.getenv("OPENROUTER_MODEL", OPENROUTER_DEFAULT_MODEL) if source == "openrouter" else settings.llm_model


def active_model() -> str:
    """The model that will answer right now (for the record kept with each AI suggestion)."""
    found = _get_client()
    return model_name(found[1]) if found else settings.llm_model


def _call_anthropic(client: anthropic.Anthropic, model: str, system: str, user: str, json_schema: dict):
    request = dict(model=model, max_tokens=MAX_TOKENS, system=system, messages=[{"role": "user", "content": user}])
    try:
        response = client.messages.create(
            **request, output_config={"effort": "low", "format": {"type": "json_schema", "schema": json_schema}}
        )
    except anthropic.BadRequestError:
        # A provider that does not take structured output: the prompt also asks for plain JSON.
        response = client.messages.create(**request)
    text = None if response.stop_reason == "refusal" else next((b.text for b in response.content if b.type == "text"), None)
    return text, response.usage.input_tokens, response.usage.output_tokens, response.stop_reason


def _call_openrouter(client: openai.OpenAI, model: str, system: str, user: str, json_schema: dict):
    request = dict(
        model=model, max_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    try:
        response = client.chat.completions.create(
            **request,
            response_format={"type": "json_schema", "json_schema": {"name": "answer", "strict": True, "schema": json_schema}},
        )
    except openai.BadRequestError:
        # This model does not take structured output: the prompt also asks for plain JSON.
        response = client.chat.completions.create(**request)
    choice = response.choices[0]
    usage = response.usage
    text = None if choice.finish_reason == "content_filter" else choice.message.content
    return text, getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None), choice.finish_reason


def _call_model(system: str, user: str, json_schema: dict, prompt_name: str) -> str | None:
    """Ask the model; returns its text, or None when no provider is configured or it declined."""
    found = _get_client()
    if found is None:
        return None
    client, source = found
    model = model_name(source)
    call = _call_openrouter if source == "openrouter" else _call_anthropic
    text, tokens_in, tokens_out, stop = call(client, model, system, user, json_schema)
    log.info("llm call prompt=%s provider=%s model=%s input_tokens=%s output_tokens=%s stop=%s",
             prompt_name, source, model, tokens_in, tokens_out, stop)
    return text

def _extract_json(text: str) -> str:
    """Tolerate a ```json fence or a sentence around the object."""
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end > start else text


def complete_json(prompt_name: str, variables: dict, schema: type[BaseModel]) -> dict | None:
    """Run prompts/<prompt_name>.md and return the answer as a validated dict, or None."""
    system, user = load_prompt(prompt_name, variables)
    try:
        text = _call_model(system, user, strict_schema(schema), prompt_name)
        if not text:
            return None
        return schema.model_validate_json(_extract_json(text)).model_dump(mode="json")
    except (anthropic.APIError, openai.OpenAIError, ValueError) as exc:  # ValueError covers pydantic's ValidationError and bad JSON
        log.warning("llm call failed prompt=%s error=%s: %s", prompt_name, type(exc).__name__, exc)
        return None
