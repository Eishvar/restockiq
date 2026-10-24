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
from app.modules.catalog.schemas import StorageAreaOut
from app.modules.settings.models import User

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


# ---------- suppliers ----------
def add_supplier(db: Session, user: User, name: str) -> Supplier:
    name = _clean(name, MAX_SUPPLIER_NAME, "supplier")
    existing = list(db.scalars(select(Supplier).where(Supplier.tenant_id == user.tenant_id)))
    if _name_taken([s.name for s in existing], name):
        raise HTTPException(409, f"You already have a supplier called {name}.")
    taken, n = {s.code for s in existing}, len(existing) + 1
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
    existing = list(db.scalars(select(Supplier).where(Supplier.tenant_id == user.tenant_id)))
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
