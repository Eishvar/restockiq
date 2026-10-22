"""Load a tenant's data from the database as the DataFrames the pure engine expects."""
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.calendar.models import CalendarEvent
from app.modules.catalog.models import Ingredient, MenuItem, Recipe, Supplier
from app.modules.inventory.models import InventoryItem
from app.modules.planning.models import SafetyProfile
from app.modules.sales.models import SalesDaily


def _frame(db: Session, stmt) -> pd.DataFrame:
    return pd.read_sql(stmt, db.connection())


def load_frames(db: Session, tenant_id: int) -> dict[str, pd.DataFrame]:
    """sales, menu, calendar, recipes, ingredients, suppliers, inventory (ids are the database ids)."""
    sales = _frame(
        db,
        select(SalesDaily.date, SalesDaily.menu_item_id.label("item_id"), SalesDaily.qty).where(
            SalesDaily.tenant_id == tenant_id
        ),
    )
    sales["date"] = pd.to_datetime(sales["date"])
    menu = _frame(
        db,
        select(MenuItem.id.label("item_id"), MenuItem.name, MenuItem.category, MenuItem.launch_date).where(
            MenuItem.tenant_id == tenant_id, MenuItem.active.is_(True)
        ),
    )
    calendar = _frame(
        db,
        select(
            CalendarEvent.type, CalendarEvent.label, CalendarEvent.start_date, CalendarEvent.end_date, CalendarEvent.name
        ).where(CalendarEvent.tenant_id == tenant_id, CalendarEvent.status == "approved"),
    )
    recipes = _frame(
        db,
        select(Recipe.menu_item_id.label("item_id"), Recipe.ingredient_id, Recipe.qty_per_serving).where(
            Recipe.tenant_id == tenant_id, Recipe.status == "approved"
        ),
    )
    ingredients = _frame(
        db,
        select(
            Ingredient.id.label("ingredient_id"),
            Ingredient.name,
            Ingredient.supplier_id,
            Ingredient.base_uom,
            Ingredient.pack_uom,
            Ingredient.pack_size_base,
            Ingredient.pack_price_rm,
            Ingredient.shelf_life_days,
        ).where(Ingredient.tenant_id == tenant_id, Ingredient.active.is_(True)),
    )
    suppliers = _frame(
        db,
        select(Supplier.id.label("supplier_id"), Supplier.name, Supplier.min_order_rm).where(
            Supplier.tenant_id == tenant_id
        ),
    )
    inventory = _frame(
        db,
        select(InventoryItem.ingredient_id, InventoryItem.qty_base, InventoryItem.last_purchased_on).where(
            InventoryItem.tenant_id == tenant_id
        ),
    )
    return dict(
        sales=sales, menu=menu, calendar=calendar, recipes=recipes,
        ingredients=ingredients, suppliers=suppliers, inventory=inventory,
    )


def load_safety(db: Session, tenant_id: int) -> pd.DataFrame:
    """Stored safety buffers in the engine's shape (buffer as a fraction)."""
    df = _frame(
        db,
        select(
            SafetyProfile.ingredient_id,
            SafetyProfile.horizon_days.label("horizon"),
            SafetyProfile.service_level,
            SafetyProfile.buffer_pct,
            SafetyProfile.n_samples,
            SafetyProfile.method,
        ).where(SafetyProfile.tenant_id == tenant_id),
    )
    df["buffer"] = df.pop("buffer_pct") / 100.0
    return df
