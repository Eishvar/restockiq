"""Suppliers and storage places that people add and rename; adding an item with them; the removed AI endpoints."""
from sqlalchemy import select

from app.modules.activity.models import ActivityLog
from app.modules.catalog.models import Ingredient, Supplier
from tests.conftest import as_user

NEW_ITEM = {
    "name": "Sweet soy sauce 2L", "storage": "dry", "base_uom": "ml", "supplier_id": None, "pack_uom": "BOTTLE (2L)",
    "pack_size_base": 2000, "pack_price_rm": 9.5, "shelf_life_days": 700, "qty_base": 4000, "last_purchased_on": "2026-10-20",
}


def actions(db):
    return [a.action for a in db.scalars(select(ActivityLog).order_by(ActivityLog.id))]


# ---------- storage places ----------
def test_the_three_standard_places_exist_and_count_their_items(client, users, loaded):
    r = client.get("/api/catalog/storage-areas", headers=as_user(users["staff"])).json()
    assert [a["key"] for a in r] == ["freezer", "chiller", "dry"]
    assert [a["name"] for a in r] == ["Freezer", "Chiller", "Dry store"]
    assert sum(a["items"] for a in r) == 74
    assert client.get("/api/catalog/storage-areas").status_code == 401


def test_add_and_rename_a_place_is_logged_and_keeps_items(client, db, users, loaded):
    manager = users["manager"]
    added = client.post("/api/catalog/storage-areas", json={"name": "  Display   fridge "}, headers=as_user(manager))
    assert added.status_code == 201 and added.json() == {"key": "display-fridge", "name": "Display fridge", "items": 0}

    renamed = client.patch("/api/catalog/storage-areas/dry", json={"name": "Pantry"}, headers=as_user(manager)).json()
    assert renamed["name"] == "Pantry" and renamed["items"] > 0  # same key, so every dry item is still there
    names = {a["key"]: a["name"] for a in client.get("/api/catalog/storage-areas", headers=as_user(manager)).json()}
    assert names["dry"] == "Pantry" and "display-fridge" in names
    assert {"storage_area_added", "storage_area_renamed"} <= set(actions(db))


def test_place_names_must_be_new_and_sensible(client, users, loaded):
    manager = users["manager"]
    assert client.post("/api/catalog/storage-areas", json={"name": "freezer"}, headers=as_user(manager)).status_code == 409
    assert client.post("/api/catalog/storage-areas", json={"name": "   "}, headers=as_user(manager)).status_code == 422
    assert client.post("/api/catalog/storage-areas", json={"name": "x" * 61}, headers=as_user(manager)).status_code == 422
    assert client.patch("/api/catalog/storage-areas/chiller", json={"name": "Freezer"}, headers=as_user(manager)).status_code == 409
    assert client.patch("/api/catalog/storage-areas/nowhere", json={"name": "Shed"}, headers=as_user(manager)).status_code == 404
    # renaming to the same name (or only changing case) is fine
    assert client.patch("/api/catalog/storage-areas/chiller", json={"name": "chiller"}, headers=as_user(manager)).status_code == 200


def test_staff_cannot_change_places_or_suppliers(client, users, loaded):
    staff = users["staff"]
    assert client.post("/api/catalog/storage-areas", json={"name": "Shed"}, headers=as_user(staff)).status_code == 403
    assert client.patch("/api/catalog/storage-areas/dry", json={"name": "Shed"}, headers=as_user(staff)).status_code == 403
    assert client.post("/api/catalog/suppliers", json={"name": "New Co"}, headers=as_user(staff)).status_code == 403
    assert client.patch("/api/catalog/suppliers/1", json={"name": "New Co"}, headers=as_user(staff)).status_code == 403


# ---------- suppliers ----------
def test_add_and_rename_a_supplier(client, db, users, loaded):
    manager = users["manager"]
    r = client.post("/api/catalog/suppliers", json={"name": " Kedah  Egg Farm "}, headers=as_user(manager))
    assert r.status_code == 201
    new = r.json()
    assert new["name"] == "Kedah Egg Farm" and new["whatsapp"] == "" and new["code"].startswith("SUP-")

    old = next(s for s in client.get("/api/catalog/suppliers", headers=as_user(manager)).json() if s["code"] == "SUP-FRZ")
    out = client.patch(f"/api/catalog/suppliers/{old['id']}", json={"name": "Utara Frozen (new name)"}, headers=as_user(manager))
    assert out.status_code == 200 and out.json()["name"] == "Utara Frozen (new name)"
    names = [s["name"] for s in client.get("/api/catalog/suppliers", headers=as_user(manager)).json()]
    assert "Kedah Egg Farm" in names and len(names) == len(set(names)) == 4
    assert {"supplier_added", "supplier_renamed"} <= set(actions(db))


def test_supplier_names_must_be_new(client, users, loaded):
    manager = users["manager"]
    existing = client.get("/api/catalog/suppliers", headers=as_user(manager)).json()
    assert client.post("/api/catalog/suppliers", json={"name": existing[0]["name"].upper()}, headers=as_user(manager)).status_code == 409
    assert client.patch(f"/api/catalog/suppliers/{existing[1]['id']}", json={"name": existing[0]["name"]}, headers=as_user(manager)).status_code == 409
    assert client.post("/api/catalog/suppliers", json={"name": ""}, headers=as_user(manager)).status_code == 422
    assert client.patch("/api/catalog/suppliers/99999", json={"name": "Nobody"}, headers=as_user(manager)).status_code == 404


def test_a_new_supplier_and_place_can_be_used_by_a_new_item(client, db, users, loaded):
    manager = users["manager"]
    supplier = client.post("/api/catalog/suppliers", json={"name": "Pasar Mini"}, headers=as_user(manager)).json()
    area = client.post("/api/catalog/storage-areas", json={"name": "Back shelf"}, headers=as_user(manager)).json()
    r = client.post("/api/inventory/items", json={**NEW_ITEM, "supplier_id": supplier["id"], "storage": area["key"]},
                    headers=as_user(manager))
    assert r.status_code == 201
    ing = db.scalars(select(Ingredient).where(Ingredient.name == "Sweet soy sauce 2L")).one()
    assert (ing.supplier_id, ing.storage) == (supplier["id"], "back-shelf")
    assert db.get(Supplier, supplier["id"]).name == "Pasar Mini"
    assert client.get("/api/catalog/storage-areas", headers=as_user(manager)).json()[-1]["items"] == 1


def test_an_item_cannot_use_a_place_that_does_not_exist(client, users, loaded):
    r = client.post("/api/inventory/items", json={**NEW_ITEM, "storage": "cellar"}, headers=as_user(users["manager"]))
    assert r.status_code == 422 and "Unknown place" in r.json()["detail"]


def test_the_bought_date_can_be_any_day_not_in_the_future(client, db, users, loaded):
    manager = users["manager"]
    ok = client.post("/api/inventory/items", json={**NEW_ITEM, "last_purchased_on": "2026-10-15"}, headers=as_user(manager))
    assert ok.status_code == 201 and ok.json()["batches"][0]["procured_on"] == "2026-10-15"
    future = client.post("/api/inventory/items", json={**NEW_ITEM, "name": "Other", "last_purchased_on": "2027-01-01"}, headers=as_user(manager))
    assert future.status_code == 422


# ---------- the AI helpers that were removed ----------
def test_the_stock_note_and_shelf_life_ai_endpoints_are_gone(client, users, loaded):
    manager = as_user(users["manager"])
    assert client.post("/api/assistant/stock-note", json={"note": "beras 12 bag"}, headers=manager).status_code in (404, 405)
    assert client.post("/api/assistant/shelf-life", json={"name": "Kicap"}, headers=manager).status_code in (404, 405)
    assert client.get("/api/assistant/status", headers=manager).status_code in (404, 405)
