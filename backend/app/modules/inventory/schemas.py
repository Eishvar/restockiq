from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class BatchRow(BaseModel):
    """One purchase of an item. Expires on procured_on + shelf_life_days."""

    id: int
    ingredient_id: int
    procured_on: date
    qty_base: float
    display_qty: str
    shelf_life_days: int
    pack_price_rm: float  # price per pack paid for this batch
    value_rm: float  # what the remaining quantity of this batch cost
    expires_on: date
    days_left: int
    status: Literal["ok", "expiring_soon", "expired"]


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
    status: Literal["ok", "expiring_soon", "expired"]  # the worst status of its batches
    expired_qty_base: float = 0
    stock_value_rm: float = 0
    batches: list[BatchRow] = []


class InventoryList(BaseModel):
    today: date
    onboarded: bool
    items: list[InventoryRow]


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    storage: str = Field(default="dry", min_length=1, max_length=20)  # a key from /catalog/storage-areas
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


class BatchCreate(BaseModel):
    """Add stock bought on one day. Missing fields default: today, the item's shelf life and pack price."""

    qty_base: float = Field(gt=0)
    procured_on: date | None = None
    shelf_life_days: int | None = Field(default=None, ge=1, le=3650)
    pack_price_rm: float | None = Field(default=None, ge=0)


class BatchPatch(BaseModel):
    """Only the fields that are sent are changed. Staff may change `qty_base` only. qty 0 removes the batch."""

    qty_base: float | None = Field(default=None, ge=0)
    procured_on: date | None = None
    shelf_life_days: int | None = Field(default=None, ge=1, le=3650)
    pack_price_rm: float | None = Field(default=None, ge=0)


class DiscardResult(BaseModel):
    discarded: list[str]  # item names
    batches: int


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
