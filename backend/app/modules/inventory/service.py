"""Inventory rules. Every quantity change writes an inventory_movement and an activity-log entry.

Stock is tracked in batches: one row per ingredient and procurement date, each with its own shelf life and
price, so each batch expires on its own date. `InventoryItem` keeps the per-ingredient totals (quantity and
latest procurement date); `_sync` recomputes them after every batch change.
"""
import re
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.activity import log_action
from app.core.clock import now_kl
from app.core.today import get_today
from app.core.units import format_qty
from app.modules.catalog import service as catalog_service
from app.modules.catalog.models import Ingredient, Supplier
from app.modules.inventory.models import InventoryBatch, InventoryItem, InventoryMovement
from app.modules.inventory.schemas import (
    BatchCreate,
    BatchPatch,
    BatchRow,
    DiscardResult,
    InventoryRow,
    ItemCreate,
    ItemPatch,
    MovementOut,
)
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


_WORST = {"ok": 0, "expiring_soon": 1, "expired": 2}


def _batch_row(ing: Ingredient, b: InventoryBatch, today: date) -> BatchRow:
    expires_on, days_left, status = compute_status(b.procured_on, b.shelf_life_days, b.qty_base, today)
    return BatchRow(
        id=b.id,
        ingredient_id=ing.id,
        procured_on=b.procured_on,
        qty_base=b.qty_base,
        display_qty=format_qty(b.qty_base, ing.base_uom),
        shelf_life_days=b.shelf_life_days,
        pack_price_rm=b.pack_price_rm,
        value_rm=round(b.qty_base / ing.pack_size_base * b.pack_price_rm, 2) if ing.pack_size_base else 0.0,
        expires_on=expires_on,
        days_left=days_left,
        status=status,
    )


def _row(ing: Ingredient, inv: InventoryItem, supplier_name: str | None, batches: list[InventoryBatch], today: date) -> InventoryRow:
    rows = [_batch_row(ing, b, today) for b in sorted(batches, key=lambda b: b.procured_on)]
    total = sum(b.qty_base for b in batches)
    # The item-level dates describe the batch that matters most: the one that expires first.
    first = min(rows, key=lambda r: r.expires_on) if rows else None
    status = max((r.status for r in rows), key=_WORST.__getitem__, default="ok")
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
        qty_base=total,
        display_qty=format_qty(total, ing.base_uom),
        last_purchased_on=max((r.procured_on for r in rows), default=None),
        shelf_life_days=ing.shelf_life_days,
        expires_on=first.expires_on if first else None,
        days_left=first.days_left if first else None,
        status=status,
        expired_qty_base=sum(r.qty_base for r in rows if r.status == "expired"),
        stock_value_rm=round(sum(r.value_rm for r in rows), 2),
        batches=rows,
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


def _batches(db: Session, tenant_id: int, ingredient_id: int | None = None) -> dict[int, list[InventoryBatch]]:
    stmt = select(InventoryBatch).where(InventoryBatch.tenant_id == tenant_id).order_by(InventoryBatch.procured_on)
    if ingredient_id is not None:
        stmt = stmt.where(InventoryBatch.ingredient_id == ingredient_id)
    out: dict[int, list[InventoryBatch]] = {}
    for b in db.scalars(stmt):
        out.setdefault(b.ingredient_id, []).append(b)
    return out


def _sync(db: Session, user: User, ingredient_id: int) -> InventoryItem:
    """Recompute the per-ingredient totals from its batches and stamp who changed it."""
    db.flush()
    batches = _batches(db, user.tenant_id, ingredient_id).get(ingredient_id, [])
    inv = db.scalars(
        select(InventoryItem).where(InventoryItem.tenant_id == user.tenant_id, InventoryItem.ingredient_id == ingredient_id)
    ).first()
    if inv is None:
        inv = InventoryItem(tenant_id=user.tenant_id, ingredient_id=ingredient_id, qty_base=0)
        db.add(inv)
    inv.qty_base = sum(b.qty_base for b in batches)
    inv.last_purchased_on = max((b.procured_on for b in batches), default=None)
    inv.updated_at, inv.updated_by = now_kl(), user.id
    return inv


def _full_row(db: Session, user: User, ingredient_id: int, today: date) -> InventoryRow:
    ing, inv, supplier_name = _one(db, user, ingredient_id)
    return _row(ing, inv, supplier_name, _batches(db, user.tenant_id, ingredient_id).get(ingredient_id, []), today)


def list_inventory(db: Session, user: User) -> tuple[date, bool, list[InventoryRow]]:
    today = get_today(db, user.tenant_id)
    tenant = db.get(Tenant, user.tenant_id)
    by_ing = _batches(db, user.tenant_id)
    rows = [_row(ing, inv, sup, by_ing.get(ing.id, []), today) for ing, inv, sup in _load(db, user)]
    return today, tenant.onboarded_at is not None, rows


def _one(db: Session, user: User, ingredient_id: int):
    found = _load(db, user, ingredient_id)
    if not found:
        raise HTTPException(404, "Item not found")
    return found[0]


def _batch(db: Session, user: User, batch_id: int) -> tuple[Ingredient, InventoryBatch]:
    b = db.get(InventoryBatch, batch_id)
    if b is None or b.tenant_id != user.tenant_id:
        raise HTTPException(404, "Batch not found")
    ing = db.get(Ingredient, b.ingredient_id)
    if ing is None or not ing.active:
        raise HTTPException(404, "Batch not found")
    return ing, b


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


def _check_not_future(procured_on: date | None, today: date) -> None:
    if procured_on is not None and procured_on > today:
        raise HTTPException(422, "The purchase date cannot be in the future")


def add_stock(
    db: Session, user: User, ing: Ingredient, qty: float, procured_on: date, reason: str, note: str,
    shelf_life_days: int | None = None, pack_price_rm: float | None = None,
) -> InventoryBatch:
    """Put stock on the shelf as a batch of its procurement date (added to that day's batch if there is one).

    Used by the Inventory page and by receiving an order. Writes the movement; the caller commits.
    """
    today = get_today(db, user.tenant_id)
    price = ing.pack_price_rm if pack_price_rm is None else pack_price_rm
    b = db.scalars(
        select(InventoryBatch).where(
            InventoryBatch.tenant_id == user.tenant_id,
            InventoryBatch.ingredient_id == ing.id,
            InventoryBatch.procured_on == procured_on,
        )
    ).first()
    if b is None:
        b = InventoryBatch(
            tenant_id=user.tenant_id, ingredient_id=ing.id, qty_base=qty, procured_on=procured_on,
            shelf_life_days=shelf_life_days or ing.shelf_life_days, pack_price_rm=price,
        )
        db.add(b)
    else:  # same item, same day: one batch; the price becomes the average weighted by quantity
        total = b.qty_base + qty
        b.pack_price_rm = (b.qty_base * b.pack_price_rm + qty * price) / total
        b.qty_base = total
    b.updated_at, b.updated_by = now_kl(), user.id
    _move(db, user, ing.id, qty, reason, today, f"{note} (batch of {procured_on.isoformat()})")
    _sync(db, user, ing.id)
    return b


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
        if supplier is None or supplier.tenant_id != user.tenant_id or not supplier.active:
            raise HTTPException(422, "Unknown supplier")
    if body.storage not in {a.key for a in catalog_service.ensure_areas(db, user.tenant_id)}:
        raise HTTPException(422, "Unknown place. Add it first, then choose it.")
    today = get_today(db, user.tenant_id)
    _check_not_future(body.last_purchased_on, today)
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
    db.add(InventoryItem(tenant_id=user.tenant_id, ingredient_id=ing.id, qty_base=0))
    tenant = db.get(Tenant, user.tenant_id)
    if body.qty_base > 0:
        reason = "onboarding" if tenant.onboarded_at is None else "adjust"
        add_stock(db, user, ing, body.qty_base, body.last_purchased_on or today, reason, "New item")
    else:
        _sync(db, user, ing.id)
    log_action(
        db, user, "inventory_item_added", "inventory", ing.id,
        {"name": ing.name, "qty_base": body.qty_base, "shelf_life_days": ing.shelf_life_days},
    )
    db.commit()
    return _full_row(db, user, ing.id, today)


def add_batch(db: Session, user: User, ingredient_id: int, body: BatchCreate) -> InventoryRow:
    """Record stock bought on one day as its own batch (merged into that day's batch if one exists)."""
    ing, _, _ = _one(db, user, ingredient_id)
    today = get_today(db, user.tenant_id)
    _check_not_future(body.procured_on, today)
    procured_on = body.procured_on or today
    b = add_stock(
        db, user, ing, body.qty_base, procured_on, "adjust", "New batch",
        shelf_life_days=body.shelf_life_days, pack_price_rm=body.pack_price_rm,
    )
    log_action(
        db, user, "inventory_batch_added", "inventory", ing.id,
        {"name": ing.name, "procured_on": procured_on.isoformat(), "qty_base": body.qty_base,
         "shelf_life_days": b.shelf_life_days, "pack_price_rm": round(b.pack_price_rm, 2)},
    )
    db.commit()
    return _full_row(db, user, ing.id, today)


def _snapshot(ing: Ingredient, batches: list[InventoryBatch]) -> dict:
    last = max((b.procured_on for b in batches), default=None)
    return {
        "qty_base": sum(b.qty_base for b in batches),
        "last_purchased_on": last.isoformat() if last else None,
        "shelf_life_days": ing.shelf_life_days,
        "pack_price_rm": ing.pack_price_rm,
    }


def _take_oldest_first(db: Session, user: User, batches: list[InventoryBatch], qty: float) -> None:
    """Remove `qty` from the batches, oldest first (that is the stock a kitchen uses first)."""
    left = qty
    for b in sorted(batches, key=lambda b: b.procured_on):
        take = min(b.qty_base, left)
        b.qty_base -= take
        left -= take
        if b.qty_base <= 1e-9:
            db.delete(b)
        if left <= 1e-9:
            break


def edit_item(
    db: Session, user: User, ingredient_id: int, body: ItemPatch, note: str = "Edited on Inventory page"
) -> InventoryRow:
    """Edit an item as a whole (quantity, purchase date, shelf life, price).

    With one batch the edit applies to that batch. With several, a new quantity adds to the batch of
    `last_purchased_on` (default: the newest) or removes the oldest stock first; to change one batch's
    date, shelf life or price, edit that batch.
    """
    sent = body.model_fields_set
    if user.role == "staff" and sent - {"qty_base"}:
        raise HTTPException(403, "Staff can update quantities only; ask a manager to change dates or shelf life")
    ing, inv, supplier_name = _one(db, user, ingredient_id)
    today = get_today(db, user.tenant_id)
    _check_not_future(body.last_purchased_on if "last_purchased_on" in sent else None, today)

    batches = _batches(db, user.tenant_id, ingredient_id).get(ingredient_id, [])
    new_date = body.last_purchased_on if "last_purchased_on" in sent else None
    if new_date and len(batches) > 1 and "qty_base" not in sent:
        raise HTTPException(409, "This item has several batches. Edit the batch whose date you want to change.")

    before = _snapshot(ing, batches)
    total = sum(b.qty_base for b in batches)
    if "qty_base" in sent and body.qty_base is not None and body.qty_base != total:
        delta = body.qty_base - total
        if len(batches) <= 1 and batches:
            b = batches[0]
            _move(db, user, ingredient_id, delta, "adjust", today, f"{note} (batch of {b.procured_on.isoformat()})")
            b.qty_base = body.qty_base
            b.updated_at, b.updated_by = now_kl(), user.id
            if b.qty_base <= 0:
                db.delete(b)
        elif delta > 0:
            on = new_date or (batches[-1].procured_on if batches else today)
            add_stock(db, user, ing, delta, on, "adjust", note)
        else:
            _move(db, user, ingredient_id, delta, "adjust", today, f"{note} (oldest stock first)")
            _take_oldest_first(db, user, batches, -delta)
        db.flush()
        batches = _batches(db, user.tenant_id, ingredient_id).get(ingredient_id, [])
    if new_date and len(batches) == 1 and batches[0].procured_on != new_date:
        batches[0].procured_on = new_date
        batches[0].updated_at, batches[0].updated_by = now_kl(), user.id
    if "shelf_life_days" in sent and body.shelf_life_days is not None:
        for b in batches:  # batches that use the item's standard shelf life follow it
            if b.shelf_life_days == ing.shelf_life_days:
                b.shelf_life_days = body.shelf_life_days
        ing.shelf_life_days = body.shelf_life_days
    if "pack_price_rm" in sent and body.pack_price_rm is not None:
        ing.pack_price_rm = body.pack_price_rm
    _sync(db, user, ingredient_id)

    after = _snapshot(ing, _batches(db, user.tenant_id, ingredient_id).get(ingredient_id, []))
    if before != after:
        log_action(db, user, "inventory_edited", "inventory", ingredient_id, {"name": ing.name, "before": before, "after": after})
    db.commit()
    return _full_row(db, user, ingredient_id, today)


def edit_batch(db: Session, user: User, batch_id: int, body: BatchPatch, note: str = "Edited on Inventory page") -> InventoryRow:
    sent = body.model_fields_set
    if user.role == "staff" and sent - {"qty_base"}:
        raise HTTPException(403, "Staff can update quantities only; ask a manager to change dates or shelf life")
    ing, b = _batch(db, user, batch_id)
    today = get_today(db, user.tenant_id)
    if "procured_on" in sent and body.procured_on is not None:
        _check_not_future(body.procured_on, today)
        clash = db.scalars(
            select(InventoryBatch).where(
                InventoryBatch.tenant_id == user.tenant_id, InventoryBatch.ingredient_id == b.ingredient_id,
                InventoryBatch.procured_on == body.procured_on, InventoryBatch.id != b.id,
            )
        ).first()
        if clash is not None:
            raise HTTPException(409, "There is already a batch of this item from that date. Edit that batch instead.")

    def snap() -> dict:
        return {"procured_on": b.procured_on.isoformat(), "qty_base": b.qty_base,
                "shelf_life_days": b.shelf_life_days, "pack_price_rm": round(b.pack_price_rm, 2)}

    before = snap()
    if "qty_base" in sent and body.qty_base is not None and body.qty_base != b.qty_base:
        _move(db, user, ing.id, body.qty_base - b.qty_base, "adjust", today, f"{note} (batch of {b.procured_on.isoformat()})")
        b.qty_base = body.qty_base
    if "procured_on" in sent and body.procured_on is not None:
        b.procured_on = body.procured_on
    if "shelf_life_days" in sent and body.shelf_life_days is not None:
        b.shelf_life_days = body.shelf_life_days
    if "pack_price_rm" in sent and body.pack_price_rm is not None:
        b.pack_price_rm = body.pack_price_rm
    b.updated_at, b.updated_by = now_kl(), user.id
    after = snap()
    if before != after:
        log_action(db, user, "inventory_batch_edited", "inventory", ing.id, {"name": ing.name, "before": before, "after": after})
    if b.qty_base <= 0:
        db.delete(b)
    _sync(db, user, ing.id)
    db.commit()
    return _full_row(db, user, ing.id, today)


def remove_batch(db: Session, user: User, batch_id: int) -> None:
    """Delete one batch (for example a delivery that was entered by mistake). The history is kept."""
    ing, b = _batch(db, user, batch_id)
    today = get_today(db, user.tenant_id)
    _move(db, user, ing.id, -b.qty_base, "removed", today, f"Batch of {b.procured_on.isoformat()} removed")
    log_action(
        db, user, "inventory_batch_removed", "inventory", ing.id,
        {"name": ing.name, "procured_on": b.procured_on.isoformat(), "qty_base": b.qty_base},
    )
    db.delete(b)
    _sync(db, user, ing.id)
    db.commit()


def remove_item(db: Session, user: User, ingredient_id: int) -> None:
    """Soft delete: the ingredient is hidden from stock, its batches are removed and the history is kept."""
    ing, inv, _ = _one(db, user, ingredient_id)
    today = get_today(db, user.tenant_id)
    batches = _batches(db, user.tenant_id, ingredient_id).get(ingredient_id, [])
    removed_qty = sum(b.qty_base for b in batches)
    if removed_qty:
        _move(db, user, ingredient_id, -removed_qty, "removed", today, "Item removed")
    for b in batches:
        db.delete(b)
    ing.active = False
    _sync(db, user, ingredient_id)
    log_action(db, user, "inventory_item_removed", "inventory", ingredient_id, {"name": ing.name, "qty_base": removed_qty})
    db.commit()


def _discard(db: Session, user: User, ing: Ingredient, b: InventoryBatch, today: date) -> None:
    expires_on = b.procured_on + timedelta(days=b.shelf_life_days)
    _move(db, user, ing.id, -b.qty_base, "discard_expired", today, f"Expired stock thrown away (batch of {b.procured_on.isoformat()})")
    log_action(
        db, user, "inventory_expired_discarded", "inventory", ing.id,
        {"name": ing.name, "qty_base": b.qty_base, "procured_on": b.procured_on.isoformat(), "expired_on": expires_on.isoformat()},
    )
    db.delete(b)


def _is_expired(b: InventoryBatch, today: date) -> bool:
    return compute_status(b.procured_on, b.shelf_life_days, b.qty_base, today)[2] == "expired"


def discard_batch(db: Session, user: User, batch_id: int) -> DiscardResult:
    """Throw away one expired batch (409 if it has not expired)."""
    ing, b = _batch(db, user, batch_id)
    today = get_today(db, user.tenant_id)
    if not _is_expired(b, today):
        raise HTTPException(409, "This batch is not expired")
    _discard(db, user, ing, b, today)
    _sync(db, user, ing.id)
    db.commit()
    return DiscardResult(discarded=[ing.name], batches=1)


def discard_expired(db: Session, user: User, ingredient_id: int | None = None) -> DiscardResult:
    """Throw away every expired batch of one item (409 if it has none) or of all items."""
    today = get_today(db, user.tenant_id)
    if ingredient_id is not None:
        _one(db, user, ingredient_id)
    by_ing = _batches(db, user.tenant_id, ingredient_id)
    names, count = [], 0
    for ing, _, _ in _load(db, user, ingredient_id):
        expired = [b for b in by_ing.get(ing.id, []) if _is_expired(b, today)]
        for b in expired:
            _discard(db, user, ing, b, today)
        if expired:
            _sync(db, user, ing.id)
            names.append(ing.name)
            count += len(expired)
    if ingredient_id is not None and not count:
        raise HTTPException(409, "This item is not expired")
    db.commit()
    return DiscardResult(discarded=names, batches=count)


def backfill_batches(db: Session) -> int:
    """One-time upgrade: stock saved before batches existed becomes one batch per item (same date, shelf life)."""
    have = set(db.scalars(select(InventoryBatch.ingredient_id).distinct()))
    created = 0
    for inv in db.scalars(select(InventoryItem).where(InventoryItem.qty_base > 0)):
        if inv.ingredient_id in have:
            continue
        ing = db.get(Ingredient, inv.ingredient_id)
        if ing is None:
            continue
        db.add(InventoryBatch(
            tenant_id=inv.tenant_id, ingredient_id=inv.ingredient_id, qty_base=inv.qty_base,
            procured_on=inv.last_purchased_on or get_today(db, inv.tenant_id),
            shelf_life_days=ing.shelf_life_days, pack_price_rm=ing.pack_price_rm,
            updated_at=inv.updated_at, updated_by=inv.updated_by,
        ))
        created += 1
    if created:
        db.commit()
    return created


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
