from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db import get_db
from app.modules.catalog.models import Ingredient, MenuItem, Recipe, Supplier
from app.modules.catalog.schemas import IngredientOut, MenuItemOut, RecipeOut, SupplierOut
from app.modules.settings.models import User

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/menu", response_model=list[MenuItemOut])
def menu(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(MenuItem).where(MenuItem.tenant_id == user.tenant_id).order_by(MenuItem.code)).all()


@router.get("/suppliers", response_model=list[SupplierOut])
def suppliers(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Supplier).where(Supplier.tenant_id == user.tenant_id).order_by(Supplier.code)).all()


@router.get("/ingredients", response_model=list[IngredientOut])
def ingredients(user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = (
        select(Ingredient, Supplier.name)
        .join(Supplier, Supplier.id == Ingredient.supplier_id, isouter=True)
        .where(Ingredient.tenant_id == user.tenant_id)
        .order_by(Ingredient.name)
    )
    return [
        IngredientOut(
            id=i.id,
            code=i.code,
            name=i.name,
            supplier_id=i.supplier_id,
            supplier_name=supplier_name,
            storage=i.storage,
            base_uom=i.base_uom,
            pack_uom=i.pack_uom,
            pack_size_base=i.pack_size_base,
            pack_price_rm=i.pack_price_rm,
            shelf_life_days=i.shelf_life_days,
            active=i.active,
        )
        for i, supplier_name in db.execute(stmt)
    ]


@router.get("/recipes", response_model=list[RecipeOut])
def recipes(menu_item_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """All recipe lines, or only one dish's when `menu_item_id` is given."""
    stmt = (
        select(Recipe, MenuItem.name, Ingredient.name, Ingredient.base_uom)
        .join(MenuItem, MenuItem.id == Recipe.menu_item_id)
        .join(Ingredient, Ingredient.id == Recipe.ingredient_id)
        .where(Recipe.tenant_id == user.tenant_id)
        .order_by(MenuItem.name, Ingredient.name)
    )
    if menu_item_id is not None:
        stmt = stmt.where(Recipe.menu_item_id == menu_item_id)
    return [
        RecipeOut(
            id=r.id,
            menu_item_id=r.menu_item_id,
            menu_item_name=item_name,
            ingredient_id=r.ingredient_id,
            ingredient_name=ing_name,
            qty_per_serving=r.qty_per_serving,
            base_uom=uom,
            status=r.status,
            source=r.source,
        )
        for r, item_name, ing_name, uom in db.execute(stmt)
    ]
