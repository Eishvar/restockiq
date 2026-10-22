from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class InventoryRow(BaseModel):
    ingredient_id: int
    code: str
    name: str
    storage: str
    supplier_id: int | None
    supplier_name: str | None
    base_uom: str
    pack_uom: str
    pack_size_base: float
    pack_price_rm: float
    qty_base: float
    display_qty: str
    last_purchased_on: date | None
    shelf_life_days: int
    expires_on: date | None
    days_left: int | None
    status: Literal["ok", "expiring_soon", "expired"]


class InventoryList(BaseModel):
    today: date
    onboarded: bool
    items: list[InventoryRow]


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    storage: Literal["freezer", "chiller", "dry"] = "dry"
    base_uom: Literal["g", "ml", "pcs"]
    supplier_id: int | None = None
    pack_uom: str = Field(min_length=1, max_length=60, description='e.g. "BAG (10kg)"')
    pack_size_base: float = Field(gt=0)
    pack_price_rm: float = Field(ge=0)
    shelf_life_days: int = Field(ge=1, le=3650)
    qty_base: float = Field(default=0, ge=0)
    last_purchased_on: date | None = None


class ItemPatch(BaseModel):
    """Only the fields that are sent are changed. Staff may change `qty_base` only."""

    qty_base: float | None = Field(default=None, ge=0)
    last_purchased_on: date | None = None
    shelf_life_days: int | None = Field(default=None, ge=1, le=3650)
    pack_price_rm: float | None = Field(default=None, ge=0)


class MovementOut(BaseModel):
    id: int
    date: date
    change_base: float
    display_change: str
    reason: str
    user_name: str | None
    note: str


class OnboardingResult(BaseModel):
    onboarded: bool
    onboarded_at: datetime | None
