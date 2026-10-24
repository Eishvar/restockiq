"""Suppliers and storage places that people can add and rename themselves.

Both are plain lists of names. A rename only changes the text people see; items keep pointing at the same row
or key, so nothing else needs updating. Every change is written to the activity log.
"""
import re

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.activity import log_action
from app.modules.catalog.models import Ingredient, StorageArea, Supplier
from app.modules.catalog.schemas import RemovedOut, StorageAreaOut, SupplierOut
from app.modules.planning.models import PurchaseOrder
from app.modules.settings.models import User

# An order in these states is waiting on a person or a supplier, so its supplier cannot be removed yet.
IN_PROGRESS = ("pending_approval", "approved", "sent")

DEFAULT_AREAS = [("freezer", "Freezer"), ("chiller", "Chiller"), ("dry", "Dry store")]
MAX_STORAGE_NAME, MAX_SUPPLIER_NAME = 60, 120


def _clean(name: str, limit: int, what: str) -> str:
    name = " ".join(name.split())
    if not name:
        raise HTTPException(422, f"Please type a name for the {what}.")
    if len(name) > limit:
        raise HTTPException(422, f"The {what} name must be {limit} characters or fewer.")
    return name


# ---------- storage places ----------
def ensure_areas(db: Session, tenant_id: int) -> list[StorageArea]:
    """The tenant's places, creating the three standard ones the first time."""
    areas = list(db.scalars(select(StorageArea).where(StorageArea.tenant_id == tenant_id).order_by(StorageArea.id)))
    if not areas:
        areas = [StorageArea(tenant_id=tenant_id, key=k, name=n) for k, n in DEFAULT_AREAS]
        db.add_all(areas)
        db.flush()
    return areas


def _area_out(db: Session, area: StorageArea) -> StorageAreaOut:
    count = db.scalar(
        select(func.count()).select_from(Ingredient).where(Ingredient.tenant_id == area.tenant_id, Ingredient.storage == area.key)
    )
    return StorageAreaOut(key=area.key, name=area.name, items=count or 0)


def list_areas(db: Session, user: User) -> list[StorageAreaOut]:
    areas = ensure_areas(db, user.tenant_id)
    db.commit()
    return [_area_out(db, a) for a in areas]


def _name_taken(names: list[str], name: str, except_name: str | None = None) -> bool:
    return any(n.lower() == name.lower() and n != except_name for n in names)


def add_area(db: Session, user: User, name: str) -> StorageAreaOut:
    name = _clean(name, MAX_STORAGE_NAME, "place")
    areas = ensure_areas(db, user.tenant_id)
    if _name_taken([a.name for a in areas], name):
        raise HTTPException(409, f"You already have a place called {name}.")
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:14] or "place"
    taken, key, n = {a.key for a in areas}, base, 2
    while key in taken:
        key, n = f"{base}-{n}", n + 1
    area = StorageArea(tenant_id=user.tenant_id, key=key, name=name)
    db.add(area)
    db.flush()
    log_action(db, user, "storage_area_added", "storage_area", key, {"name": name})
    db.commit()
    return _area_out(db, area)


def rename_area(db: Session, user: User, key: str, name: str) -> StorageAreaOut:
    name = _clean(name, MAX_STORAGE_NAME, "place")
    areas = ensure_areas(db, user.tenant_id)
    area = next((a for a in areas if a.key == key), None)
    if area is None:
        raise HTTPException(404, "That place does not exist")
    if _name_taken([a.name for a in areas], name, except_name=area.name):
        raise HTTPException(409, f"You already have a place called {name}.")
    if area.name != name:
        log_action(db, user, "storage_area_renamed", "storage_area", key, {"before": area.name, "after": name})
        area.name = name
    db.commit()
    return _area_out(db, area)


def remove_area(db: Session, user: User, key: str, move_to: str | None) -> RemovedOut:
    """Remove a place. Items kept there must be moved to another place first (move_to)."""
    areas = ensure_areas(db, user.tenant_id)
    area = next((a for a in areas if a.key == key), None)
    if area is None:
        raise HTTPException(404, "That place does not exist")
    if len(areas) == 1:
        raise HTTPException(409, "You need at least one place to keep stock in.")
    items = list(db.scalars(select(Ingredient).where(Ingredient.tenant_id == user.tenant_id, Ingredient.storage == key)))
    target = None
    if items:
        if move_to is None:
            raise HTTPException(409, f"{len(items)} item(s) are kept in {area.name}. Choose another place to move them to.")
        target = next((a for a in areas if a.key == move_to and a.key != key), None)
        if target is None:
            raise HTTPException(422, "Choose a different place to move the items to.")
        for ing in items:
            ing.storage = target.key
    log_action(
        db, user, "storage_area_removed", "storage_area", key,
        {"name": area.name, "moved_items": len(items), "moved_to": target.name if target else None},
    )
    db.delete(area)
    db.commit()
    return RemovedOut(removed=area.name, moved_items=len(items), moved_to=target.name if target else None)


# ---------- suppliers ----------
def _active_suppliers(db: Session, tenant_id: int) -> list[Supplier]:
    return list(db.scalars(select(Supplier).where(Supplier.tenant_id == tenant_id, Supplier.active.is_(True)).order_by(Supplier.code)))


def list_suppliers(db: Session, user: User) -> list[SupplierOut]:
    counts = dict(
        db.execute(
            select(Ingredient.supplier_id, func.count()).where(Ingredient.tenant_id == user.tenant_id).group_by(Ingredient.supplier_id)
        ).all()
    )
    return [SupplierOut.model_validate(s, from_attributes=True).model_copy(update={"items": counts.get(s.id, 0)})
            for s in _active_suppliers(db, user.tenant_id)]


def remove_supplier(db: Session, user: User, supplier_id: int, move_to: int | None) -> RemovedOut:
    """Hide a supplier. Blocked while an order with it is in progress; its items must move to another supplier."""
    active = _active_suppliers(db, user.tenant_id)
    supplier = next((s for s in active if s.id == supplier_id), None)
    if supplier is None:
        raise HTTPException(404, "Supplier not found")
    orders = list(
        db.scalars(select(PurchaseOrder).where(PurchaseOrder.supplier_id == supplier_id, PurchaseOrder.status.in_(IN_PROGRESS + ("draft",))))
    )
    in_progress = [o for o in orders if o.status in IN_PROGRESS]
    if in_progress:
        raise HTTPException(409, f"{supplier.name} has {len(in_progress)} order(s) in progress. Finish or reject them first.")
    items = list(db.scalars(select(Ingredient).where(Ingredient.tenant_id == user.tenant_id, Ingredient.supplier_id == supplier_id)))
    target = None
    if items:
        if move_to is None:
            raise HTTPException(409, f"{len(items)} item(s) are bought from {supplier.name}. Choose another supplier to move them to.")
        target = next((s for s in active if s.id == move_to and s.id != supplier_id), None)
        if target is None:
            raise HTTPException(422, "Choose a different supplier to move the items to.")
        for ing in items:
            ing.supplier_id = target.id
    for order in orders:  # unsent drafts for this supplier would have nowhere to go
        order.status, order.reject_reason = "rejected", "Supplier removed"
    supplier.active = False
    log_action(
        db, user, "supplier_removed", "supplier", supplier.id,
        {"name": supplier.name, "moved_items": len(items), "moved_to": target.name if target else None,
         "drafts_closed": len(orders)},
    )
    db.commit()
    return RemovedOut(removed=supplier.name, moved_items=len(items), moved_to=target.name if target else None)


def add_supplier(db: Session, user: User, name: str) -> Supplier:
    name = _clean(name, MAX_SUPPLIER_NAME, "supplier")
    everyone = list(db.scalars(select(Supplier).where(Supplier.tenant_id == user.tenant_id)))
    existing = [s for s in everyone if s.active]
    if _name_taken([s.name for s in existing], name):
        raise HTTPException(409, f"You already have a supplier called {name}.")
    taken, n = {s.code for s in everyone}, len(everyone) + 1
    while f"SUP-{n}" in taken:
        n += 1
    supplier = Supplier(tenant_id=user.tenant_id, code=f"SUP-{n}", name=name)
    db.add(supplier)
    db.flush()
    log_action(db, user, "supplier_added", "supplier", supplier.id, {"name": name})
    db.commit()
    return supplier


def rename_supplier(db: Session, user: User, supplier_id: int, name: str) -> Supplier:
    name = _clean(name, MAX_SUPPLIER_NAME, "supplier")
    existing = _active_suppliers(db, user.tenant_id)
    supplier = next((s for s in existing if s.id == supplier_id), None)
    if supplier is None:
        raise HTTPException(404, "Supplier not found")
    if _name_taken([s.name for s in existing], name, except_name=supplier.name):
        raise HTTPException(409, f"You already have a supplier called {name}.")
    if supplier.name != name:
        log_action(db, user, "supplier_renamed", "supplier", supplier.id, {"before": supplier.name, "after": name})
        supplier.name = name
    db.commit()
    return supplier
