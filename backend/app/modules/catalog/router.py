from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import current_user, require_role
from app.db import get_db
from app.modules.catalog import recipes as recipe_service
from app.modules.catalog import service
from app.modules.catalog.models import Ingredient, MenuItem, Recipe, Supplier
from app.modules.catalog.schemas import (
    DishIn, DishRecipeOut, IngredientOut, MenuItemOut, NameIn, RecipeOut, RecipeSaveIn, RemovedOut, StorageAreaOut, SupplierOut,
)
from app.modules.planning import refresh
from app.modules.settings.models import User
from app.modules.setup.models import TenantSetup

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/menu", response_model=list[MenuItemOut])
def menu(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(MenuItem).where(MenuItem.tenant_id == user.tenant_id).order_by(MenuItem.code)).all()


@router.get("/suppliers", response_model=list[SupplierOut])
def suppliers(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.list_suppliers(db, user)


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def add_supplier(body: NameIn, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    """Add a supplier by name. Its WhatsApp number and minimum order are filled in later under Supplier details."""
    return service.add_supplier(db, user, body.name)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
def rename_supplier(supplier_id: int, body: NameIn, user: User = Depends(require_role("manager")),
                    db: Session = Depends(get_db)):
    return service.rename_supplier(db, user, supplier_id, body.name)


@router.delete("/suppliers/{supplier_id}", response_model=RemovedOut)
def remove_supplier(supplier_id: int, move_to: int | None = None, user: User = Depends(require_role("owner")),
                    db: Session = Depends(get_db)):
    """Owner: remove a supplier. Pass `move_to` (another supplier's id) when it still has items."""
    return service.remove_supplier(db, user, supplier_id, move_to)


@router.delete("/storage-areas/{key}", response_model=RemovedOut)
def remove_storage_area(key: str, move_to: str | None = None, user: User = Depends(require_role("owner")),
                        db: Session = Depends(get_db)):
    """Owner: remove a place. Pass `move_to` (another place's key) when items are kept there."""
    return service.remove_area(db, user, key, move_to)


@router.get("/storage-areas", response_model=list[StorageAreaOut])
def storage_areas(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The places stock can be kept (Freezer, Chiller, Dry store and any the business added)."""
    return service.list_areas(db, user)


@router.post("/storage-areas", response_model=StorageAreaOut, status_code=201)
def add_storage_area(body: NameIn, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    return service.add_area(db, user, body.name)


@router.patch("/storage-areas/{key}", response_model=StorageAreaOut)
def rename_storage_area(key: str, body: NameIn, user: User = Depends(require_role("manager")),
                        db: Session = Depends(get_db)):
    return service.rename_area(db, user, key, body.name)


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


@router.get("/recipe-book", response_model=list[DishRecipeOut])
def recipe_book(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Every dish with its recipe (an empty one for a dish that has none yet). Everyone can read it."""
    return recipe_service.recipe_book(db, user)


@router.put("/menu/{menu_item_id}/recipe", response_model=DishRecipeOut)
def save_recipe(menu_item_id: int, body: RecipeSaveIn, background: BackgroundTasks,
                user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    """Replace the ingredients of one dish. Takes effect in the next plan."""
    dish, changed = recipe_service.save_recipe(db, user, menu_item_id, body.lines)
    setup = db.get(TenantSetup, user.tenant_id)
    # During first-time setup the buffers are re-measured once when the recipes are confirmed, not after every edit.
    if changed and setup is not None and setup.setup_done_at is not None:
        background.add_task(refresh.run_recompute, user.tenant_id, user.id, "recipe")
    return dish


@router.post("/menu", response_model=DishRecipeOut, status_code=201)
def add_dish(body: DishIn, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    """Add a new dish with its recipe. Sales files can then include it (matched by name)."""
    return recipe_service.add_dish(db, user, body.name, body.category, body.price_rm, body.lines)


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
