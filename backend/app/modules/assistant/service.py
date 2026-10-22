"""AI helpers for messy human input. The LLM only reads text; a person confirms; code does the maths.

- stock note  -> review rows (nothing is saved until a manager applies them)
- new item    -> shelf-life / storage / unit suggestion (nothing is saved until the item is added)
"""
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import llm
from app.config import settings
from app.core.activity import log_action
from app.core.clock import now_kl
from app.core.today import get_today
from app.core.units import to_base
from app.modules.assistant.models import AISuggestion
from app.modules.assistant.schemas import (
    ApplyIn,
    ApplyOut,
    LlmShelfLife,
    LlmStockNote,
    NoteOut,
    ReviewRow,
    ShelfLifeIn,
    ShelfLifeOut,
)
from app.modules.catalog.models import Ingredient
from app.modules.inventory.models import InventoryItem
from app.modules.inventory.schemas import ItemPatch
from app.modules.inventory.service import edit_item
from app.modules.settings.models import User

UNAVAILABLE = "The AI helper is unavailable right now. Please enter this by hand instead."
FAMILY = {"g": "g", "kg": "g", "ml": "ml", "l": "ml", "pcs": "pcs"}  # typed unit -> base unit it belongs to
RANK = {"high": 2, "medium": 1, "low": 0}


def _lower(confidence: str, to: str) -> str:
    return confidence if RANK[confidence] <= RANK[to] else to


def _suggestion(db: Session, user: User, suggestion_id: int, kind: str) -> AISuggestion:
    s = db.get(AISuggestion, suggestion_id)
    if s is None or s.tenant_id != user.tenant_id or s.kind != kind:
        raise HTTPException(404, "Suggestion not found")
    return s


# ---------- stock note ----------
def _review_row(index: int, raw, ingredients: dict[int, Ingredient], stock: dict[int, float], today: date) -> ReviewRow:
    issues: list[str] = []
    confidence = raw["confidence"]
    ing = ingredients.get(raw["ingredient_id"]) if raw["ingredient_id"] is not None else None

    qty, unit, qty_base = raw["qty"], raw["unit"], None
    if ing is None:
        issues.append("Not in your stock list. Add it with + Add item.")
        confidence = _lower(confidence, "low")
    elif qty is None or unit is None or qty < 0:
        issues.append("No amount found in the note.")
        confidence = _lower(confidence, "low")
    elif unit == "pack":
        qty_base = to_base(qty, "pack", ing.pack_size_base)  # packs x the pack size from your own item list
    elif FAMILY[unit] == ing.base_uom:
        qty_base = to_base(qty, unit)
    else:
        issues.append(f"'{unit}' does not fit {ing.name}, which is counted in {ing.base_uom}.")
        confidence = _lower(confidence, "low")

    bought = None
    if raw["last_purchased_on"]:
        try:
            bought = date.fromisoformat(raw["last_purchased_on"])
        except ValueError:
            bought = None
        if bought is None or bought > today:
            issues.append("The date in the note could not be used, so it was left blank.")
            bought, confidence = None, _lower(confidence, "medium")

    return ReviewRow(
        index=index, ingredient_id=ing.id if ing else None, ingredient_name=ing.name if ing else None,
        new_item_name=raw["new_item_name"] if ing is None else None, raw_text=raw["raw_text"], qty=qty, unit=unit,
        qty_base=qty_base, last_purchased_on=bought, confidence=confidence, issue=" ".join(issues) or None,
        current_qty_base=stock.get(ing.id) if ing else None,
    )


def parse_stock_note(db: Session, user: User, note: str) -> NoteOut:
    if not llm.ai_available():
        raise HTTPException(503, UNAVAILABLE)
    today = get_today(db, user.tenant_id)
    ingredients = {
        i.id: i for i in db.scalars(select(Ingredient).where(Ingredient.tenant_id == user.tenant_id, Ingredient.active.is_(True)))
    }
    stock = {
        s.ingredient_id: s.qty_base
        for s in db.scalars(select(InventoryItem).where(InventoryItem.tenant_id == user.tenant_id))
    }
    result = llm.complete_json(
        "stock_note",
        {
            "today": today.isoformat(), "today_name": today.strftime("%A"), "note": note,
            "ingredients": [{"id": i.id, "name": i.name, "base_uom": i.base_uom, "pack_uom": i.pack_uom} for i in ingredients.values()],
        },
        LlmStockNote,
    )
    if result is None:
        raise HTTPException(503, UNAVAILABLE)

    rows = [_review_row(n, r, ingredients, stock, today) for n, r in enumerate(result["rows"])]
    suggestion = AISuggestion(
        tenant_id=user.tenant_id, kind="stock_note", input_text=note, status="pending", model=settings.llm_model,
        payload={"rows": [r.model_dump(mode="json") for r in rows]}, created_at=now_kl(),
    )
    db.add(suggestion)
    db.flush()
    log_action(
        db, user, "ai_stock_note_read", "ai_suggestion", suggestion.id,
        {"rows": len(rows), "matched": sum(r.ingredient_id is not None for r in rows)},
    )
    db.commit()
    return NoteOut(suggestion_id=suggestion.id, model=settings.llm_model, rows=rows)


def apply_stock_note(db: Session, user: User, suggestion_id: int, body: ApplyIn) -> ApplyOut:
    """Save the rows a person checked (and maybe edited): the quantity on the shelf becomes the quantity in the note."""
    suggestion = _suggestion(db, user, suggestion_id, "stock_note")
    if suggestion.status != "pending":
        raise HTTPException(409, f"This note was already {suggestion.status}.")
    today = get_today(db, user.tenant_id)
    ingredients = {
        i.id: i for i in db.scalars(select(Ingredient).where(Ingredient.tenant_id == user.tenant_id, Ingredient.active.is_(True)))
    }
    seen: set[int] = set()
    for r in body.rows:  # check everything before saving anything
        if r.ingredient_id not in ingredients:
            raise HTTPException(422, "One of the items is not in your stock list")
        if r.ingredient_id in seen:
            raise HTTPException(422, f"{ingredients[r.ingredient_id].name} appears twice. Keep one row for each item.")
        if r.last_purchased_on and r.last_purchased_on > today:
            raise HTTPException(422, "The purchase date cannot be in the future")
        seen.add(r.ingredient_id)

    for r in body.rows:
        patch = {"qty_base": r.qty_base}
        if r.last_purchased_on is not None:
            patch["last_purchased_on"] = r.last_purchased_on
        edit_item(db, user, r.ingredient_id, ItemPatch(**patch), note="From a stock note")

    suggestion.status, suggestion.decided_by = "applied", user.id
    names = [ingredients[r.ingredient_id].name for r in body.rows]
    log_action(db, user, "ai_suggestion_applied", "ai_suggestion", suggestion.id, {"kind": "stock_note", "items": names})
    db.commit()
    return ApplyOut(applied=len(names), items=names)


def dismiss_suggestion(db: Session, user: User, suggestion_id: int) -> dict:
    s = db.get(AISuggestion, suggestion_id)
    if s is None or s.tenant_id != user.tenant_id:
        raise HTTPException(404, "Suggestion not found")
    if s.status != "pending":
        raise HTTPException(409, f"This suggestion was already {s.status}.")
    s.status, s.decided_by = "dismissed", user.id
    log_action(db, user, "ai_suggestion_dismissed", "ai_suggestion", s.id, {"kind": s.kind})
    db.commit()
    return {"status": "dismissed"}


# ---------- shelf life for a new item ----------
def suggest_shelf_life(db: Session, user: User, body: ShelfLifeIn) -> ShelfLifeOut:
    if not llm.ai_available():
        raise HTTPException(503, UNAVAILABLE)
    result = llm.complete_json(
        "shelf_life", {"name": body.name, "description": body.description or "(none)"}, LlmShelfLife
    )
    if result is None:
        raise HTTPException(503, UNAVAILABLE)
    suggestion = AISuggestion(
        tenant_id=user.tenant_id, kind="shelf_life", input_text=body.name, payload=result, status="pending",
        model=settings.llm_model, created_at=now_kl(),
    )
    db.add(suggestion)
    db.flush()
    log_action(db, user, "ai_shelf_life_suggested", "ai_suggestion", suggestion.id,
               {"item": body.name, "shelf_life_days": result["shelf_life_days"]})
    db.commit()
    return ShelfLifeOut(suggestion_id=suggestion.id, **result)
