from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]


# ---------- what the LLM must return (validated in ai/llm.py) ----------
class LlmRow(BaseModel):
    ingredient_id: int | None
    new_item_name: str | None
    raw_text: str
    qty: float | None
    unit: Literal["g", "kg", "ml", "l", "pcs", "pack"] | None
    last_purchased_on: str | None
    confidence: Confidence


class LlmStockNote(BaseModel):
    rows: list[LlmRow] = Field(max_length=60)


class LlmShelfLife(BaseModel):
    shelf_life_days: int = Field(ge=1, le=3650)
    storage: Literal["freezer", "chiller", "dry"]
    base_uom: Literal["g", "ml", "pcs"]
    rationale: str


# ---------- API ----------
class StatusOut(BaseModel):
    available: bool


class NoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class ReviewRow(BaseModel):
    """One row for the person to check. Amounts come from the note's own numbers, converted by code."""

    index: int
    ingredient_id: int | None
    ingredient_name: str | None
    new_item_name: str | None
    raw_text: str
    qty: float | None
    unit: str | None
    qty_base: float | None
    last_purchased_on: date | None
    confidence: Confidence
    issue: str | None
    current_qty_base: float | None


class NoteOut(BaseModel):
    suggestion_id: int
    model: str
    rows: list[ReviewRow]


class ApplyRow(BaseModel):
    ingredient_id: int
    qty_base: float = Field(ge=0)
    last_purchased_on: date | None = None


class ApplyIn(BaseModel):
    rows: list[ApplyRow] = Field(min_length=1, max_length=100)


class ApplyOut(BaseModel):
    applied: int
    items: list[str]


class ShelfLifeIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=300)


class ShelfLifeOut(BaseModel):
    suggestion_id: int
    shelf_life_days: int
    storage: str
    base_uom: str
    rationale: str
