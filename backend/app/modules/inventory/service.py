"""Inventory rules. Every quantity change writes an inventory_movement and an activity-log entry."""
import re
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.activity import log_action
from app.core.clock import now_kl
from app.core.today import get_today
from app.core.units import format_qty
from app.modules.catalog.models import Ingredient, Supplier
from app.modules.inventory.models import InventoryItem, InventoryMovement
from app.modules.inventory.schemas import InventoryRow, ItemCreate, ItemPatch, MovementOut
from app.modules.settings.models import Tenant, User

EXPIRING_SOON_DAYS = 2


def compute_status(
    last_purchased_on: date | None, shelf_life_days: int, qty_base: float, today: date
) -> tuple[date | None, int | None, str]:
    """Return (expires_on, days_left, status).

    Expiry = last_purchased_on + shelf_life_days; stock is expired on that day (matches the purchasing
    rule "expiry <= today => not usable"). `expiring_soon` means 1-2 days left. An empty shelf
    (qty 0) or an unknown purchase date has nothing that can expire, so it is "ok".
    """
    if last_purchased_on is None:
        return None, None, "ok"
    expires_on = last_purchased_on + timedelta(days=shelf_life_days)
    days_left = (expires_on - today).days
    if qty_base <= 0:
        return expires_on, days_left, "ok"
    if days_left <= 0:
        return expires_on, days_left, "expired"
    if days_left <= EXPIRING_SOON_DAYS:
        return expires_on, days_left, "expiring_soon"
    return expires_on, days_left, "ok"


def _row(ing: Ingredient, inv: InventoryItem, supplier_name: str | None, today: date) -> InventoryRow:
    expires_on, days_left, status = compute_status(inv.last_purchased_on, ing.shelf_life_days, inv.qty_base, today)
    return InventoryRow(
        ingredient_id=ing.id,
        code=ing.code,
        name=ing.name,
        storage=ing.storage,
        supplier_id=ing.supplier_id,
        supplier_name=supplier_name,
        base_uom=ing.base_uom,
        pack_uom=ing.pack_uom,
        pack_size_base=ing.pack_size_base,
        pack_price_rm=ing.pack_price_rm,
        qty_base=inv.qty_base,
        display_qty=format_qty(inv.qty_base, ing.base_uom),
        last_purchased_on=inv.last_purchased_on,
        shelf_life_days=ing.shelf_life_days,
        expires_on=expires_on,
        days_left=days_left,
        status=status,
    )


def _load(db: Session, user: User, ingredient_id: int | None = None):
    stmt = (
        select(Ingredient, InventoryItem, Supplier.name)
        .join(InventoryItem, InventoryItem.ingredient_id == Ingredient.id)
        .join(Supplier, Supplier.id == Ingredient.supplier_id, isouter=True)
        .where(Ingredient.tenant_id == user.tenant_id, Ingredient.active.is_(True))
        .order_by(Ingredient.name)
    )
    if ingredient_id is not None:
        stmt = stmt.where(Ingredient.id == ingredient_id)
    return db.execute(stmt).all()


def list_inventory(db: Session, user: User) -> tuple[date, bool, list[InventoryRow]]:
    today = get_today(db, user.tenant_id)
    tenant = db.get(Tenant, user.tenant_id)
    rows = [_row(ing, inv, sup, today) for ing, inv, sup in _load(db, user)]
    return today, tenant.onboarded_at is not None, rows


def _one(db: Session, user: User, ingredient_id: int):
    found = _load(db, user, ingredient_id)
    if not found:
        raise HTTPException(404, "Item not found")
    return found[0]


def _move(db: Session, user: User, ingredient_id: int, change: float, reason: str, today: date, note: str = ""):
    db.add(
        InventoryMovement(
            tenant_id=user.tenant_id,
            ingredient_id=ingredient_id,
            date=today,
            change_base=change,
            reason=reason,
            user_id=user.id,
            note=note,
        )
    )


def _make_code(db: Session, tenant_id: int, name: str) -> str:
    base = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")[:50] or "ITEM"
    taken = set(db.scalars(select(Ingredient.code).where(Ingredient.tenant_id == tenant_id)))
    code, n = base, 2
    while code in taken:
        code, n = f"{base}_{n}", n + 1
    return code


def add_item(db: Session, user: User, body: ItemCreate) -> InventoryRow:
    if body.supplier_id is not None:
        supplier = db.get(Supplier, body.supplier_id)
        if supplier is None or supplier.tenant_id != user.tenant_id:
            raise HTTPException(422, "Unknown supplier")
    today = get_today(db, user.tenant_id)
    ing = Ingredient(
        tenant_id=user.tenant_id,
        code=_make_code(db, user.tenant_id, body.name),
        name=body.name.strip(),
        supplier_id=body.supplier_id,
        storage=body.storage,
        base_uom=body.base_uom,
        pack_uom=body.pack_uom,
        pack_size_base=body.pack_size_base,
        pack_price_rm=body.pack_price_rm,
        shelf_life_days=body.shelf_life_days,
        active=True,
    )
    db.add(ing)
    db.flush()
    last = body.last_purchased_on or (today if body.qty_base > 0 else None)
    inv = InventoryItem(
        tenant_id=user.tenant_id,
        ingredient_id=ing.id,
        qty_base=body.qty_base,
        last_purchased_on=last,
        updated_at=now_kl(),
        updated_by=user.id,
    )
    db.add(inv)
    tenant = db.get(Tenant, user.tenant_id)
    if body.qty_base:
        reason = "onboarding" if tenant.onboarded_at is None else "adjust"
        _move(db, user, ing.id, body.qty_base, reason, today, "New item")
    log_action(
        db, user, "inventory_item_added", "inventory", ing.id,
        {"name": ing.name, "qty_base": body.qty_base, "shelf_life_days": ing.shelf_life_days},
    )
    db.commit()
    return _row(ing, inv, db.get(Supplier, ing.supplier_id).name if ing.supplier_id else None, today)


def edit_item(db: Session, user: User, ingredient_id: int, body: ItemPatch) -> InventoryRow:
    sent = body.model_fields_set
    if user.role == "staff" and sent - {"qty_base"}:
        raise HTTPException(403, "Staff can update quantities only; ask a manager to change dates or shelf life")
    ing, inv, supplier_name = _one(db, user, ingredient_id)
    today = get_today(db, user.tenant_id)
    if "last_purchased_on" in sent and body.last_purchased_on and body.last_purchased_on > today:
        raise HTTPException(422, "The purchase date cannot be in the future")

    before = {
        "qty_base": inv.qty_base,
        "last_purchased_on": inv.last_purchased_on.isoformat() if inv.last_purchased_on else None,
        "shelf_life_days": ing.shelf_life_days,
        "pack_price_rm": ing.pack_price_rm,
    }
    if "qty_base" in sent and body.qty_base is not None and body.qty_base != inv.qty_base:
        _move(db, user, ingredient_id, body.qty_base - inv.qty_base, "adjust", today, "Edited on Inventory page")
        inv.qty_base = body.qty_base
    if "last_purchased_on" in sent:
        inv.last_purchased_on = body.last_purchased_on
    if "shelf_life_days" in sent and body.shelf_life_days is not None:
        ing.shelf_life_days = body.shelf_life_days
    if "pack_price_rm" in sent and body.pack_price_rm is not None:
        ing.pack_price_rm = body.pack_price_rm
    inv.updated_at, inv.updated_by = now_kl(), user.id

    after = {
        "qty_base": inv.qty_base,
        "last_purchased_on": inv.last_purchased_on.isoformat() if inv.last_purchased_on else None,
        "shelf_life_days": ing.shelf_life_days,
        "pack_price_rm": ing.pack_price_rm,
    }
    if before != after:
        log_action(db, user, "inventory_edited", "inventory", ingredient_id, {"name": ing.name, "before": before, "after": after})
    db.commit()
    return _row(ing, inv, supplier_name, today)


def remove_item(db: Session, user: User, ingredient_id: int) -> None:
    """Soft delete: the ingredient is hidden from stock, its quantity is zeroed and the history is kept."""
    ing, inv, _ = _one(db, user, ingredient_id)
    today = get_today(db, user.tenant_id)
    if inv.qty_base:
        _move(db, user, ingredient_id, -inv.qty_base, "removed", today, "Item removed")
    removed_qty = inv.qty_base
    inv.qty_base, inv.updated_at, inv.updated_by = 0, now_kl(), user.id
    ing.active = False
    log_action(db, user, "inventory_item_removed", "inventory", ingredient_id, {"name": ing.name, "qty_base": removed_qty})
    db.commit()


def _discard(db: Session, user: User, ing: Ingredient, inv: InventoryItem, today: date) -> float:
    qty = inv.qty_base
    _move(db, user, ing.id, -qty, "discard_expired", today, "Expired stock thrown away")
    inv.qty_base, inv.updated_at, inv.updated_by = 0, now_kl(), user.id
    log_action(
        db, user, "inventory_expired_discarded", "inventory", ing.id,
        {"name": ing.name, "qty_base": qty, "expired_on": (inv.last_purchased_on + timedelta(days=ing.shelf_life_days)).isoformat()},
    )
    return qty


def discard_expired(db: Session, user: User, ingredient_id: int | None = None) -> list[str]:
    """Throw away expired stock for one ingredient (404/409 if it is not expired) or for all of them."""
    today = get_today(db, user.tenant_id)
    if ingredient_id is not None:
        ing, inv, _ = _one(db, user, ingredient_id)
        if compute_status(inv.last_purchased_on, ing.shelf_life_days, inv.qty_base, today)[2] != "expired":
            raise HTTPException(409, "This item is not expired")
        targets = [(ing, inv)]
    else:
        targets = [
            (ing, inv)
            for ing, inv, _ in _load(db, user)
            if compute_status(inv.last_purchased_on, ing.shelf_life_days, inv.qty_base, today)[2] == "expired"
        ]
    names = []
    for ing, inv in targets:
        _discard(db, user, ing, inv, today)
        names.append(ing.name)
    db.commit()
    return names


def movements(db: Session, user: User, ingredient_id: int) -> list[MovementOut]:
    ing, _, _ = _one(db, user, ingredient_id)
    stmt = (
        select(InventoryMovement, User.name)
        .join(User, User.id == InventoryMovement.user_id, isouter=True)
        .where(InventoryMovement.tenant_id == user.tenant_id, InventoryMovement.ingredient_id == ingredient_id)
        .order_by(InventoryMovement.id.desc())
    )
    return [
        MovementOut(
            id=m.id,
            date=m.date,
            change_base=m.change_base,
            display_change=("+" if m.change_base > 0 else "-" if m.change_base < 0 else "") + format_qty(abs(m.change_base), ing.base_uom),
            reason=m.reason,
            user_name=name,
            note=m.note,
        )
        for m, name in db.execute(stmt)
    ]


def confirm_onboarding(db: Session, user: User) -> Tenant:
    tenant = db.get(Tenant, user.tenant_id)
    if tenant.onboarded_at is None:
        tenant.onboarded_at = now_kl()
        count = len(_load(db, user))
        log_action(db, user, "onboarding_confirmed", "tenant", tenant.id, {"items": count})
        db.commit()
    return tenant
