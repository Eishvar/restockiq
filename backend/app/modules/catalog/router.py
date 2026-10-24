from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import current_user, require_role
from app.db import get_db
from app.modules.catalog import service
from app.modules.catalog.models import Ingredient, MenuItem, Recipe, Supplier
from app.modules.catalog.schemas import IngredientOut, MenuItemOut, NameIn, RecipeOut, StorageAreaOut, SupplierOut
from app.modules.settings.models import User

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/menu", response_model=list[MenuItemOut])
def menu(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(MenuItem).where(MenuItem.tenant_id == user.tenant_id).order_by(MenuItem.code)).all()


@router.get("/suppliers", response_model=list[SupplierOut])
def suppliers(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Supplier).where(Supplier.tenant_id == user.tenant_id).order_by(Supplier.code)).all()


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def add_supplier(body: NameIn, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    """Add a supplier by name. Its WhatsApp number and minimum order are filled in later under Supplier details."""
    return service.add_supplier(db, user, body.name)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
def rename_supplier(supplier_id: int, body: NameIn, user: User = Depends(require_role("manager")),
                    db: Session = Depends(get_db)):
    return service.rename_supplier(db, user, supplier_id, body.name)


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
