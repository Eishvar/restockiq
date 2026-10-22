"""Load the synthetic demo data (data/*.csv) into the database.

    cd backend && python -m app.seed.load --reset       # wipe everything, reload (also after schema changes)
    cd backend && python -m app.seed.load --if-empty    # load only when no menu exists (used on deploy)

`load_demo_data()` expects the data tables to be empty; `reset_demo_data()` empties them first but keeps
the users, so a signed-in browser stays signed in after "Reset demo data".
"""
import argparse
import csv
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.clock import now_kl
from app.db import Base, SessionLocal, engine, import_all_models, init_db
from app.modules.calendar.models import CalendarEvent
from app.modules.catalog.models import Ingredient, MenuItem, Recipe, Supplier
from app.modules.inventory.models import InventoryItem, InventoryMovement
from app.modules.planning.quality import recompute_safety
from app.modules.sales.models import SalesDaily
from app.modules.settings.models import Tenant, User
from app.seed.demo import ensure_demo_tenant

CHUNK = 5000
KEEP_ON_RESET = {Tenant.__tablename__, User.__tablename__}


def _rows(name: str, data_dir: Path) -> list[dict[str, str]]:
    with open(data_dir / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _date(text: str) -> date | None:
    return date.fromisoformat(text) if text else None


def _bulk(db: Session, model, rows: list[dict]) -> None:
    for i in range(0, len(rows), CHUNK):
        db.execute(insert(model), rows[i : i + CHUNK])


def table_counts(db: Session, tenant_id: int) -> dict[str, int]:
    return {
        label: db.scalar(select(func.count()).select_from(model).where(model.tenant_id == tenant_id)) or 0
        for label, model in [
            ("menu_items", MenuItem),
            ("suppliers", Supplier),
            ("ingredients", Ingredient),
            ("recipes", Recipe),
            ("sales_daily", SalesDaily),
            ("calendar_events", CalendarEvent),
            ("inventory_items", InventoryItem),
            ("inventory_movements", InventoryMovement),
        ]
    }


def is_empty(db: Session) -> bool:
    return (db.scalar(select(func.count()).select_from(MenuItem)) or 0) == 0


def load_demo_data(db: Session, data_dir: Path | None = None, compute_safety: bool = True) -> dict[str, int]:
    """Insert tenant settings, catalog, sales, calendar and opening inventory. Returns row counts.

    `compute_safety` runs the backtest that fills safety buffers (a few seconds); tests switch it off.
    """
    data_dir = data_dir or settings.data_dir
    tenant = ensure_demo_tenant(db)
    tid = tenant.id
    tenant.risk_profile = "balanced"
    tenant.manual_planning_hours = 16
    tenant.onboarded_at = None  # so the first-time inventory setup shows in the demo
    tenant.today_override = None

    _bulk(
        db,
        Supplier,
        [
            dict(
                tenant_id=tid,
                code=r["supplier_id"],
                name=r["name"],
                category=r["category"],
                delivery_days=r["delivery_days"],
                lead_time_days=int(r["lead_time_days"]),
                min_order_rm=float(r["min_order_rm"]),
                whatsapp=r["whatsapp"],
            )
            for r in _rows("suppliers.csv", data_dir)
        ],
    )
    supplier_id = {s.code: s.id for s in db.scalars(select(Supplier).where(Supplier.tenant_id == tid))}

    _bulk(
        db,
        MenuItem,
        [
            dict(
                tenant_id=tid,
                code=r["item_id"],
                name=r["name"],
                category=r["category"],
                price_rm=float(r["price_rm"]),
                launch_date=_date(r["launch_date"]),
                active=True,
            )
            for r in _rows("menu_items.csv", data_dir)
        ],
    )
    menu_id = {m.code: m.id for m in db.scalars(select(MenuItem).where(MenuItem.tenant_id == tid))}

    _bulk(
        db,
        Ingredient,
        [
            dict(
                tenant_id=tid,
                code=r["ingredient_id"],
                name=r["name"],
                supplier_id=supplier_id[r["supplier_id"]],
                storage=r["storage"],
                base_uom=r["base_uom"],
                pack_uom=r["pack_uom"],
                pack_size_base=float(r["pack_size_base"]),
                pack_price_rm=float(r["pack_price_rm"]),
                shelf_life_days=int(r["shelf_life_days"]),
                active=True,
            )
            for r in _rows("ingredients.csv", data_dir)
        ],
    )
    ingredient_id = {i.code: i.id for i in db.scalars(select(Ingredient).where(Ingredient.tenant_id == tid))}

    _bulk(
        db,
        Recipe,
        [
            dict(
                tenant_id=tid,
                menu_item_id=menu_id[r["item_id"]],
                ingredient_id=ingredient_id[r["ingredient_id"]],
                qty_per_serving=float(r["qty_per_serving"]),
                status="approved",
                source="seed",
            )
            for r in _rows("recipes.csv", data_dir)
        ],
    )

    _bulk(
        db,
        SalesDaily,
        [
            dict(
                tenant_id=tid,
                date=date.fromisoformat(r["date"]),
                menu_item_id=menu_id[r["item_id"]],
                qty=int(r["qty"]),
                net_sales_rm=float(r["net_sales_rm"]),
            )
            for r in _rows("daily_sales.csv", data_dir)
        ],
    )

    _bulk(
        db,
        CalendarEvent,
        [
            dict(
                tenant_id=tid,
                type=r["type"],
                label=r["label"] or None,
                start_date=date.fromisoformat(r["start_date"]),
                end_date=date.fromisoformat(r["end_date"]),
                name=r["name"],
                status="approved",
                source="seed",
            )
            for r in _rows("calendar_events.csv", data_dir)
        ],
    )

    stamp = now_kl()
    inventory = _rows("inventory.csv", data_dir)
    _bulk(
        db,
        InventoryItem,
        [
            dict(
                tenant_id=tid,
                ingredient_id=ingredient_id[r["ingredient_id"]],
                qty_base=float(r["qty_base"]),
                last_purchased_on=_date(r["last_purchased_date"]),
                updated_at=stamp,
            )
            for r in inventory
        ],
    )
    _bulk(
        db,
        InventoryMovement,
        [
            dict(
                tenant_id=tid,
                ingredient_id=ingredient_id[r["ingredient_id"]],
                date=date.fromisoformat(r["counted_on"]),
                change_base=float(r["qty_base"]),
                reason="onboarding",
                note="Opening stock",
            )
            for r in inventory
        ],
    )
    db.commit()

    if compute_safety:
        recompute_safety(db, tenant)
        db.commit()
    return table_counts(db, tid)


def reset_demo_data(db: Session, compute_safety: bool = True) -> dict[str, int]:
    """Delete all data except tenants and users, then reload the demo data."""
    import_all_models()
    for table in reversed(Base.metadata.sorted_tables):
        if table.name not in KEEP_ON_RESET:
            db.execute(delete(table))
    db.commit()
    return load_demo_data(db, compute_safety=compute_safety)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the synthetic demo data.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--reset", action="store_true", help="drop all tables and reload everything")
    group.add_argument("--if-empty", action="store_true", help="load only if the database has no menu yet")
    args = parser.parse_args()

    import_all_models()
    if args.reset:
        Base.metadata.drop_all(engine)
    init_db()
    with SessionLocal() as db:
        if args.if_empty and not is_empty(db):
            print("Database already has data; nothing to do.")
            return
        started = datetime.now()
        counts = load_demo_data(db)
        print(f"Loaded in {(datetime.now() - started).total_seconds():.1f}s:", counts)


if __name__ == "__main__":
    main()
