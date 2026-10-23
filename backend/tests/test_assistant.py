"""AI helpers with the model mocked: happy path, unknown item, AI unavailable, and the human-in-the-loop rules."""
import json

import pytest
from pydantic import BaseModel
from sqlalchemy import select

from app.ai import llm
from app.modules.activity.models import ActivityLog
from app.modules.assistant.models import AISuggestion
from app.modules.assistant.schemas import LlmStockNote
from app.modules.inventory.models import InventoryItem, InventoryMovement
from tests.conftest import as_user

NOTE = "beras 12 bag, telur 3 tray beli semalam, ayam 2 ctn isnin"


@pytest.fixture()
def fake_ai(monkeypatch):
    """Pretend an AI provider exists. Set `ai.answer` to a dict/str (or a function of (prompt_name, user_text))."""

    class Fake:
        answer = None
        calls: list = []

    fake = Fake()
    fake.calls = []

    def call(system, user, json_schema, prompt_name):
        fake.calls.append({"system": system, "user": user, "schema": json_schema, "prompt": prompt_name})
        out = fake.answer(prompt_name, user) if callable(fake.answer) else fake.answer
        return out if isinstance(out, str) or out is None else json.dumps(out)

    monkeypatch.setattr(llm, "_call_model", call)
    monkeypatch.setattr(llm, "ai_available", lambda: True)
    return fake


@pytest.fixture()
def no_ai(monkeypatch):
    for var in ("AI_INTEGRATIONS_ANTHROPIC_API_KEY", "AI_INTEGRATIONS_ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def ingredient(client, users, code):
    rows = client.get("/api/catalog/ingredients", headers=as_user(users["staff"])).json()
    return next(i for i in rows if i["code"] == code)


def row(ing_id, raw, qty, unit, date=None, conf="high", new=None):
    return {"ingredient_id": ing_id, "new_item_name": new, "raw_text": raw, "qty": qty, "unit": unit,
            "last_purchased_on": date, "confidence": conf}


def read_note(client, user, note=NOTE):
    return client.post("/api/assistant/stock-note", json={"note": note}, headers=as_user(user))


# ---------- happy path ----------
def test_example_note_gives_reviewable_rows_with_amounts_converted_by_code(client, db, users, loaded, fake_ai):
    rice, egg, chicken = (ingredient(client, users, c) for c in ("RICE", "EGG", "CHICKEN_BREAST"))
    fake_ai.answer = {"rows": [
        row(rice["id"], "beras 12 bag", 12, "pack"),
        row(egg["id"], "telur 3 tray beli semalam", 3, "pack", "2026-10-21"),
        row(chicken["id"], "ayam 2 ctn isnin", 2, "pack", "2026-10-19", "medium"),
    ]}
    r = read_note(client, users["staff"])  # staff may read a note
    assert r.status_code == 200, r.text
    out = r.json()
    rows = out["rows"]
    assert [x["ingredient_name"] for x in rows] == [rice["name"], egg["name"], chicken["name"]]
    assert rows[0]["qty_base"] == 12 * rice["pack_size_base"]  # packs x pack size: code, not the model, does the maths
    assert rows[1]["qty_base"] == 3 * egg["pack_size_base"] and rows[1]["last_purchased_on"] == "2026-10-21"
    assert rows[2]["last_purchased_on"] == "2026-10-19" and rows[2]["confidence"] == "medium"
    assert all(x["issue"] is None and x["current_qty_base"] is not None for x in rows)

    # what the model was shown: today's date and weekday, the ingredient list and the note
    sent = fake_ai.calls[0]
    assert sent["prompt"] == "stock_note" and "Thursday 2026-10-22" in sent["user"] and NOTE in sent["user"]
    assert f'"id": {rice["id"]}' in sent["user"]
    assert sent["schema"]["additionalProperties"] is False  # structured-output schema is closed

    # saved as a pending suggestion, nothing in stock changed yet, one log entry
    s = db.get(AISuggestion, out["suggestion_id"])
    assert s.kind == "stock_note" and s.status == "pending" and s.input_text == NOTE and len(s.payload["rows"]) == 3
    inv = db.scalars(select(InventoryItem).where(InventoryItem.ingredient_id == rice["id"])).one()
    assert inv.qty_base != 12 * rice["pack_size_base"]
    log = db.scalars(select(ActivityLog).where(ActivityLog.action == "ai_stock_note_read")).one()
    assert log.role == "staff" and log.details == {"rows": 3, "matched": 3}


def test_weights_and_volumes_are_converted_from_their_own_units(client, users, loaded, fake_ai):
    rice = ingredient(client, users, "RICE")  # counted in grams
    fake_ai.answer = {"rows": [row(rice["id"], "beras 2.5 kg", 2.5, "kg")]}
    got = read_note(client, users["manager"]).json()["rows"][0]
    assert got["qty_base"] == 2500 and got["issue"] is None


# ---------- unknown items and bad rows ----------
def test_unknown_item_is_shown_but_flagged_and_not_applicable(client, users, loaded, fake_ai):
    fake_ai.answer = {"rows": [
        row(None, "kicap manis 2 btl", 2, "pack", new="Kicap manis", conf="medium"),
        row(999999, "something odd 1 pcs", 1, "pcs"),  # an id the model made up
    ]}
    rows = read_note(client, users["manager"]).json()["rows"]
    assert rows[0]["ingredient_id"] is None and rows[0]["new_item_name"] == "Kicap manis"
    assert rows[0]["qty_base"] is None and "Not in your stock list" in rows[0]["issue"] and rows[0]["confidence"] == "low"
    assert rows[1]["ingredient_id"] is None and rows[1]["ingredient_name"] is None  # invented ids are dropped


def test_row_problems_are_caught_by_code_and_lower_confidence(client, users, loaded, fake_ai):
    egg, rice = ingredient(client, users, "EGG"), ingredient(client, users, "RICE")
    fake_ai.answer = {"rows": [
        row(egg["id"], "telur 2 kg", 2, "kg"),  # eggs are counted in pieces
        row(rice["id"], "beras", None, None),  # no amount in the note
        row(rice["id"], "beras 3 bag esok", 3, "pack", "2026-11-30"),  # a date after today
        row(rice["id"], "beras 3 bag lusa", 3, "pack", "not-a-date"),
    ]}
    r = read_note(client, users["manager"]).json()["rows"]
    assert r[0]["qty_base"] is None and "does not fit" in r[0]["issue"] and r[0]["confidence"] == "low"
    assert r[1]["qty_base"] is None and r[1]["issue"] == "No amount found in the note." and r[1]["confidence"] == "low"
    assert r[2]["last_purchased_on"] is None and r[2]["qty_base"] == 3 * rice["pack_size_base"] and r[2]["confidence"] == "medium"
    assert r[3]["last_purchased_on"] is None and "date" in r[3]["issue"]


# ---------- AI unavailable ----------
def test_status_and_503_when_no_provider_is_configured(client, users, loaded, no_ai):
    assert client.get("/api/assistant/status", headers=as_user(users["staff"])).json() == {"available": False}
    r = read_note(client, users["manager"])
    assert r.status_code == 503 and "enter this by hand" in r.json()["detail"]
    r = client.post("/api/assistant/shelf-life", json={"name": "Kicap manis 2L"}, headers=as_user(users["manager"]))
    assert r.status_code == 503


def test_status_true_with_a_provider(client, users, loaded, fake_ai):
    assert client.get("/api/assistant/status", headers=as_user(users["staff"])).json() == {"available": True}


@pytest.mark.parametrize("answer", [
    None,  # no answer / refusal
    "I'm sorry, I can't do that.",  # not JSON
    {"rows": [{"ingredient_id": 1}]},  # missing fields
    {"rows": [row(1, "x", 1, "bucket")]},  # unit not allowed
])
def test_a_bad_answer_is_treated_as_unavailable_and_saves_nothing(client, db, users, loaded, fake_ai, answer):
    fake_ai.answer = answer
    assert read_note(client, users["manager"]).status_code == 503
    assert db.scalars(select(AISuggestion)).all() == []


def test_note_needs_text(client, users, loaded, fake_ai):
    assert client.post("/api/assistant/stock-note", json={"note": ""}, headers=as_user(users["manager"])).status_code == 422
    assert client.post("/api/assistant/stock-note", json={"note": "x" * 2001}, headers=as_user(users["manager"])).status_code == 422
    assert client.post("/api/assistant/stock-note", json={"note": "x"}).status_code == 401


# ---------- applying: a person decides ----------
def prepared(client, users, fake_ai):
    rice, egg = ingredient(client, users, "RICE"), ingredient(client, users, "EGG")
    fake_ai.answer = {"rows": [row(rice["id"], "beras 12 bag", 12, "pack", "2026-10-21"),
                                row(egg["id"], "telur 3 tray", 3, "pack")]}
    out = read_note(client, users["staff"]).json()
    return out["suggestion_id"], rice, egg, out["rows"]


def apply(client, user, sid, rows):
    return client.post(f"/api/assistant/suggestions/{sid}/apply", json={"rows": rows}, headers=as_user(user))


def test_staff_cannot_apply_but_a_manager_can_and_edits_win(client, db, users, loaded, fake_ai):
    sid, rice, egg, rows = prepared(client, users, fake_ai)
    payload = [{"ingredient_id": rice["id"], "qty_base": 9_000, "last_purchased_on": "2026-10-21"},  # edited down from 12 bags
               {"ingredient_id": egg["id"], "qty_base": rows[1]["qty_base"]}]
    assert apply(client, users["staff"], sid, payload).status_code == 403
    assert db.get(AISuggestion, sid).status == "pending"

    r = apply(client, users["manager"], sid, payload)
    assert r.status_code == 200 and r.json() == {"applied": 2, "items": [rice["name"], egg["name"]]}
    inv = {i.ingredient_id: i for i in db.scalars(select(InventoryItem))}
    assert inv[rice["id"]].qty_base == 9_000 and inv[rice["id"]].last_purchased_on.isoformat() == "2026-10-21"
    assert inv[egg["id"]].qty_base == rows[1]["qty_base"]
    assert inv[egg["id"]].last_purchased_on is not None  # no date in the note: the old one is kept

    # movements and the log tell the story
    move = db.scalars(select(InventoryMovement).where(InventoryMovement.ingredient_id == rice["id"],
                                                      InventoryMovement.reason == "adjust")).one()
    assert move.note.startswith("From a stock note") and move.user_id == users["manager"].id
    actions = [a.action for a in db.scalars(select(ActivityLog).order_by(ActivityLog.id))]
    assert actions[0] == "ai_stock_note_read" and "inventory_edited" in actions and actions[-1] == "ai_suggestion_applied"
    done = db.scalars(select(ActivityLog).where(ActivityLog.action == "ai_suggestion_applied")).one()
    assert done.role == "manager" and done.details["items"] == [rice["name"], egg["name"]]
    s = db.get(AISuggestion, sid)
    assert s.status == "applied" and s.decided_by == users["manager"].id


def test_a_suggestion_can_only_be_applied_once(client, users, loaded, fake_ai):
    sid, rice, _, _ = prepared(client, users, fake_ai)
    rows = [{"ingredient_id": rice["id"], "qty_base": 100}]
    assert apply(client, users["manager"], sid, rows).status_code == 200
    assert apply(client, users["manager"], sid, rows).status_code == 409
    assert client.post(f"/api/assistant/suggestions/{sid}/dismiss", headers=as_user(users["manager"])).status_code == 409


def test_apply_checks_everything_before_saving_anything(client, db, users, loaded, fake_ai):
    sid, rice, egg, _ = prepared(client, users, fake_ai)
    before = {i.ingredient_id: i.qty_base for i in db.scalars(select(InventoryItem))}
    good = {"ingredient_id": rice["id"], "qty_base": 1}
    for bad in (
        {"ingredient_id": 999999, "qty_base": 5},  # not in the stock list
        {"ingredient_id": egg["id"], "qty_base": 5, "last_purchased_on": "2026-12-01"},  # future date
        {"ingredient_id": rice["id"], "qty_base": 5},  # rice twice
    ):
        assert apply(client, users["manager"], sid, [good, bad]).status_code == 422
    assert apply(client, users["manager"], sid, [{"ingredient_id": rice["id"], "qty_base": -1}]).status_code == 422
    assert apply(client, users["manager"], sid, []).status_code == 422
    after = {i.ingredient_id: i.qty_base for i in db.scalars(select(InventoryItem))}
    assert after == before and db.get(AISuggestion, sid).status == "pending"


def test_apply_unknown_suggestion_or_wrong_kind(client, users, loaded, fake_ai):
    assert apply(client, users["manager"], 9999, [{"ingredient_id": 1, "qty_base": 1}]).status_code == 404
    fake_ai.answer = {"shelf_life_days": 30, "storage": "dry", "base_uom": "g", "rationale": "ok"}
    shelf = client.post("/api/assistant/shelf-life", json={"name": "Mystery powder"}, headers=as_user(users["manager"])).json()
    assert apply(client, users["manager"], shelf["suggestion_id"], [{"ingredient_id": 1, "qty_base": 1}]).status_code == 404


def test_dismiss_a_note(client, db, users, loaded, fake_ai):
    sid, *_ = prepared(client, users, fake_ai)
    assert client.post(f"/api/assistant/suggestions/{sid}/dismiss", headers=as_user(users["staff"])).status_code == 403
    assert client.post(f"/api/assistant/suggestions/{sid}/dismiss", headers=as_user(users["manager"])).status_code == 200
    assert db.get(AISuggestion, sid).status == "dismissed"
    assert db.scalars(select(ActivityLog).where(ActivityLog.action == "ai_suggestion_dismissed")).one().role == "manager"


# ---------- shelf life ----------
NEW_ITEM = {"name": "Kicap manis 2L", "storage": "dry", "base_uom": "ml", "pack_uom": "BTL (2L)",
            "pack_size_base": 2000, "pack_price_rm": 9.5, "shelf_life_days": 700, "qty_base": 0}


def test_shelf_life_suggestion_is_only_a_suggestion_until_the_item_is_added(client, db, users, loaded, fake_ai):
    fake_ai.answer = {"shelf_life_days": 730, "storage": "dry", "base_uom": "ml",
                      "rationale": "Sealed bottled sauce, stays good for about two years."}
    r = client.post("/api/assistant/shelf-life", json={"name": "Kicap manis 2L bottle", "description": "sealed"},
                    headers=as_user(users["manager"]))
    assert r.status_code == 200
    s = r.json()
    assert (s["shelf_life_days"], s["storage"], s["base_uom"]) == (730, "dry", "ml") and "two years" in s["rationale"]
    assert "Kicap manis 2L bottle" in fake_ai.calls[0]["user"] and fake_ai.calls[0]["prompt"] == "shelf_life"
    assert db.get(AISuggestion, s["suggestion_id"]).status == "pending"
    from app.modules.catalog.models import Ingredient
    assert db.scalars(select(Ingredient).where(Ingredient.name == "Kicap manis 2L")).first() is None  # nothing created

    # the person edits the days to 700 and adds the item: the suggestion is marked accepted and logged
    added = client.post("/api/inventory/items", json={**NEW_ITEM, "suggestion_id": s["suggestion_id"]},
                        headers=as_user(users["manager"]))
    assert added.status_code == 201
    assert db.get(AISuggestion, s["suggestion_id"]).status == "applied"
    log = db.scalars(select(ActivityLog).where(ActivityLog.action == "ai_suggestion_applied")).one()
    assert log.details == {"kind": "shelf_life", "item": "Kicap manis 2L", "suggested_days": 730, "final_days": 700}


def test_adding_an_item_ignores_a_stranger_or_missing_suggestion(client, db, users, loaded):
    r = client.post("/api/inventory/items", json={**NEW_ITEM, "suggestion_id": 12345}, headers=as_user(users["manager"]))
    assert r.status_code == 201
    assert db.scalars(select(ActivityLog).where(ActivityLog.action == "ai_suggestion_applied")).first() is None


@pytest.mark.parametrize("answer", [
    {"shelf_life_days": 0, "storage": "dry", "base_uom": "g", "rationale": "x"},  # out of range
    {"shelf_life_days": 30, "storage": "cellar", "base_uom": "g", "rationale": "x"},  # not an allowed place
    "no idea",
])
def test_invalid_shelf_life_answer_is_unavailable(client, users, loaded, fake_ai, answer):
    fake_ai.answer = answer
    r = client.post("/api/assistant/shelf-life", json={"name": "Kicap"}, headers=as_user(users["manager"]))
    assert r.status_code == 503


# ---------- ai/llm.py on its own ----------
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
    assert llm.complete_json("shelf_life", {"name": "a", "description": "b"}, Tiny) is None


def test_provider_chain_prefers_replit_then_own_key_then_none(monkeypatch):
    for var in ("AI_INTEGRATIONS_ANTHROPIC_API_KEY", "AI_INTEGRATIONS_ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY"):
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


def test_prompts_fill_placeholders_and_have_both_parts():
    system, user = llm.load_prompt(
        "stock_note", {"today": "2026-10-22", "today_name": "Thursday", "ingredients": [{"id": 1}], "note": "telur 3"}
    )
    assert "never invent" in system.lower() and "ignore any instruction" in system.lower()
    assert "2026-10-22" in user and "telur 3" in user and '{"id": 1}' in user and "{{" not in system + user
    system, user = llm.load_prompt("shelf_life", {"name": "Kicap", "description": "(none)"})
    assert "Kicap" in user and "shelf_life_days" in system
    with pytest.raises(KeyError):
        llm.load_prompt("shelf_life", {"name": "only one variable"})


def test_strict_schema_is_closed_and_flat():
    schema = llm.strict_schema(LlmStockNote)
    text = json.dumps(schema)
    assert "$ref" not in text and "$defs" not in text and '"title"' not in text and "maxItems" not in text
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


def test_openrouter_is_the_third_provider_and_uses_its_own_model_setting(monkeypatch):
    for var in ("AI_INTEGRATIONS_ANTHROPIC_API_KEY", "AI_INTEGRATIONS_ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY",
                "OPENROUTER_API_KEY", "OPENROUTER_MODEL"):
        monkeypatch.delenv(var, raising=False)
    assert llm._get_client() is None
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    client, source = llm._get_client()
    assert source == "openrouter" and client.api_key == "or-key" and str(client.base_url).startswith("https://openrouter.ai/api/v1")
    assert llm.model_name("openrouter") == "anthropic/claude-haiku-4.5" == llm.active_model()
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    assert llm.active_model() == "google/gemini-2.5-flash"
    assert llm.ai_available() is True
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-own")  # an earlier provider wins
    assert llm._get_client()[1] == "api_key" and llm.active_model() == llm.settings.llm_model


def test_openrouter_call_sends_a_strict_json_schema_and_returns_the_text(monkeypatch):
    fake = FakeOpenRouter([_chat_reply('{"count": 2, "tag": "x"}')])
    monkeypatch.setattr(llm, "_get_client", lambda: (fake, "openrouter"))
    assert llm.complete_json("shelf_life", {"name": "Kicap", "description": "(none)"}, Tiny) == {"count": 2, "tag": "x"}
    sent = fake.requests[0]
    assert sent["model"] == "anthropic/claude-haiku-4.5"
    assert [m["role"] for m in sent["messages"]] == ["system", "user"] and "Kicap" in sent["messages"][1]["content"]
    fmt = sent["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"]["additionalProperties"] is False


def test_openrouter_model_without_json_mode_is_retried_in_plain_text(monkeypatch):
    import httpx
    err = openai_bad_request(httpx)
    fake = FakeOpenRouter([_chat_reply('Here you go: {"count": 5, "tag": null}')], fail_first_with=err)
    monkeypatch.setattr(llm, "_get_client", lambda: (fake, "openrouter"))
    assert llm.complete_json("shelf_life", {"name": "a", "description": "b"}, Tiny) == {"count": 5, "tag": None}
    assert len(fake.requests) == 2 and "response_format" not in fake.requests[1]


def openai_bad_request(httpx):
    import openai
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return openai.BadRequestError("json_schema not supported", response=httpx.Response(400, request=request), body=None)


def test_openrouter_errors_and_filtered_answers_become_none(monkeypatch):
    import httpx
    import openai
    boom = FakeOpenRouter([], fail_first_with=openai.APIConnectionError(request=httpx.Request("POST", "https://x")))
    monkeypatch.setattr(llm, "_get_client", lambda: (boom, "openrouter"))
    assert llm.complete_json("shelf_life", {"name": "a", "description": "b"}, Tiny) is None  # network failure
    filtered = FakeOpenRouter([_chat_reply("irrelevant", finish="content_filter")])
    monkeypatch.setattr(llm, "_get_client", lambda: (filtered, "openrouter"))
    assert llm.complete_json("shelf_life", {"name": "a", "description": "b"}, Tiny) is None
    junk = FakeOpenRouter([_chat_reply("no json at all")])
    monkeypatch.setattr(llm, "_get_client", lambda: (junk, "openrouter"))
    assert llm.complete_json("shelf_life", {"name": "a", "description": "b"}, Tiny) is None


def test_the_suggestion_records_the_model_that_answered(client, db, users, loaded, fake_ai, monkeypatch):
    monkeypatch.setattr(llm, "_get_client", lambda: (object(), "openrouter"))
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    rice = ingredient(client, users, "RICE")
    fake_ai.answer = {"rows": [row(rice["id"], "beras 2 kg", 2, "kg")]}
    out = read_note(client, users["manager"]).json()
    assert out["model"] == "google/gemini-2.5-flash" and db.get(AISuggestion, out["suggestion_id"]).model == "google/gemini-2.5-flash"
