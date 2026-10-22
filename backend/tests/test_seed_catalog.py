import csv
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.modules.activity.models import ActivityLog
from app.modules.calendar.models import CalendarEvent
from app.modules.inventory.models import InventoryItem, InventoryMovement
from app.modules.sales.models import SalesDaily
from app.modules.settings.models import Tenant
from app.seed.load import is_empty, load_demo_data, reset_demo_data
from tests.conftest import as_user


def csv_rows(name):
    with open(settings.data_dir / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_row_counts_match_csv_files(loaded):
    assert loaded["menu_items"] == len(csv_rows("menu_items.csv"))
    assert loaded["suppliers"] == len(csv_rows("suppliers.csv"))
    assert loaded["ingredients"] == len(csv_rows("ingredients.csv"))
    assert loaded["recipes"] == len(csv_rows("recipes.csv"))
    assert loaded["sales_daily"] == len(csv_rows("daily_sales.csv"))
    assert loaded["calendar_events"] == len(csv_rows("calendar_events.csv"))
    assert loaded["inventory_items"] == loaded["inventory_movements"] == len(csv_rows("inventory.csv"))


def test_total_sales_is_about_641k(db, loaded):
    total = db.scalar(select(func.sum(SalesDaily.net_sales_rm)))
    assert 630_000 < total < 650_000


def test_sales_expected_totals_match_csv_exactly(db, loaded):
    expected = sum(float(r["net_sales_rm"]) for r in csv_rows("daily_sales.csv"))
    assert db.scalar(select(func.sum(SalesDaily.net_sales_rm))) == pytest.approx(expected)


def test_tenant_starts_not_onboarded_with_defaults(db, loaded):
    tenant = db.scalars(select(Tenant)).one()
    assert tenant.onboarded_at is None
    assert tenant.risk_profile == "balanced" and tenant.manual_planning_hours == 16


def test_opening_inventory_movements_are_onboarding(db, loaded):
    reasons = set(db.scalars(select(InventoryMovement.reason)))
    assert reasons == {"onboarding"}
    item = db.scalars(select(InventoryItem)).first()
    assert item.last_purchased_on is not None and item.qty_base >= 0


def test_calendar_labels_loaded(db, loaded):
    labels = set(db.scalars(select(CalendarEvent.label).where(CalendarEvent.type == "period")))
    assert {"semester", "break", "intake"} <= labels


def test_is_empty_before_and_after(db):
    assert is_empty(db)
    load_demo_data(db)
    assert not is_empty(db)


def test_reset_reloads_and_keeps_users(db, users, loaded):
    before = loaded
    db.add(ActivityLog(tenant_id=1, ts=datetime.now(), action="noise"))
    db.commit()
    after = reset_demo_data(db, compute_safety=False)
    assert after == before  # same data, no duplicates
    assert db.scalar(select(func.count()).select_from(ActivityLog)) == 0  # log cleared
    assert {u.id for u in users.values()} == {1, 2, 3}  # users untouched


# ---------- catalog API ----------
def test_catalog_endpoints(client, users, loaded):
    h = as_user(users["staff"])
    menu = client.get("/api/catalog/menu", headers=h).json()
    assert len(menu) == loaded["menu_items"] and {"code", "name", "price_rm"} <= menu[0].keys()
    sup = client.get("/api/catalog/suppliers", headers=h).json()
    assert {s["code"] for s in sup} == {"SUP-FRZ", "SUP-DRY", "SUP-FRS"}
    ing = client.get("/api/catalog/ingredients", headers=h).json()
    assert len(ing) == loaded["ingredients"]
    assert all(i["supplier_name"] for i in ing)
    rec = client.get("/api/catalog/recipes", headers=h).json()
    assert len(rec) == loaded["recipes"]
    one = client.get(f"/api/catalog/recipes?menu_item_id={rec[0]['menu_item_id']}", headers=h).json()
    assert one and all(r["menu_item_id"] == rec[0]["menu_item_id"] for r in one)


def test_catalog_needs_login(client, loaded):
    assert client.get("/api/catalog/menu").status_code == 401


# ---------- admin reset ----------
def test_admin_reset_owner_only_and_logged(client, db, users, loaded):
    assert client.post("/api/admin/reset", headers=as_user(users["manager"])).status_code == 403
    assert client.post("/api/admin/reset", headers=as_user(users["staff"])).status_code == 403
    r = client.post("/api/admin/reset", headers=as_user(users["owner"]))
    assert r.status_code == 200 and r.json()["rows"] == loaded
    log = db.scalars(select(ActivityLog)).all()
    assert [(x.action, x.user_id, x.role) for x in log] == [("demo_data_reset", users["owner"].id, "owner")]
