from datetime import date

from pydantic import BaseModel, ConfigDict


class MenuItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    category: str
    price_rm: float
    launch_date: date | None
    active: bool


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    category: str
    delivery_days: str
    lead_time_days: int
    min_order_rm: float
    whatsapp: str
    items: int = 0  # how many ingredients are bought from this supplier


class RemovedOut(BaseModel):
    removed: str
    moved_items: int
    moved_to: str | None


class NameIn(BaseModel):
    name: str


class StorageAreaOut(BaseModel):
    key: str
    name: str
    items: int  # how many ingredients are kept here


class IngredientOut(BaseModel):
    id: int
    code: str
    name: str
    supplier_id: int | None
    supplier_name: str | None
    storage: str
    base_uom: str
    pack_uom: str
    pack_size_base: float
    pack_price_rm: float
    shelf_life_days: int
    active: bool


class RecipeOut(BaseModel):
    id: int
    menu_item_id: int
    menu_item_name: str
    ingredient_id: int
    ingredient_name: str
    qty_per_serving: float
    base_uom: str
    status: str
    source: str
