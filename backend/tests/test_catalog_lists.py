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


# ---------- removing a place ----------
def test_only_the_owner_can_remove_a_place_or_supplier(client, users, loaded):
    assert client.delete("/api/catalog/storage-areas/chiller?move_to=dry", headers=as_user(users["manager"])).status_code == 403
    assert client.delete("/api/catalog/suppliers/1?move_to=2", headers=as_user(users["manager"])).status_code == 403


def test_removing_a_place_moves_its_items_to_the_chosen_place(client, db, users, loaded):
    owner = as_user(users["owner"])
    need = client.delete("/api/catalog/storage-areas/chiller", headers=owner)
    assert need.status_code == 409 and "Choose another place" in need.json()["detail"]
    assert client.delete("/api/catalog/storage-areas/chiller?move_to=chiller", headers=owner).status_code == 422
    assert client.delete("/api/catalog/storage-areas/chiller?move_to=nowhere", headers=owner).status_code == 422

    before = {a["key"]: a["items"] for a in client.get("/api/catalog/storage-areas", headers=owner).json()}
    done = client.delete("/api/catalog/storage-areas/chiller?move_to=dry", headers=owner)
    assert done.json() == {"removed": "Chiller", "moved_items": before["chiller"], "moved_to": "Dry store"}
    after = {a["key"]: a["items"] for a in client.get("/api/catalog/storage-areas", headers=owner).json()}
    assert "chiller" not in after and after["dry"] == before["dry"] + before["chiller"]
    assert "storage_area_removed" in actions(db)


def test_an_empty_place_is_removed_without_moving_and_the_last_place_stays(client, users, loaded):
    owner = as_user(users["owner"])
    client.post("/api/catalog/storage-areas", json={"name": "Spare shelf"}, headers=owner)
    assert client.delete("/api/catalog/storage-areas/spare-shelf", headers=owner).json()["moved_items"] == 0
    client.delete("/api/catalog/storage-areas/freezer?move_to=dry", headers=owner)
    client.delete("/api/catalog/storage-areas/chiller?move_to=dry", headers=owner)
    last = client.delete("/api/catalog/storage-areas/dry", headers=owner)
    assert last.status_code == 409 and "at least one place" in last.json()["detail"]


# ---------- removing a supplier ----------
def supplier(client, user, code):
    return next(s for s in client.get("/api/catalog/suppliers", headers=as_user(user)).json() if s["code"] == code)


def test_removing_a_supplier_needs_somewhere_to_move_its_items(client, db, users, loaded):
    owner = users["owner"]
    frz, dry = supplier(client, owner, "SUP-FRZ"), supplier(client, owner, "SUP-DRY")
    assert frz["items"] > 0
    need = client.delete(f"/api/catalog/suppliers/{frz['id']}", headers=as_user(owner))
    assert need.status_code == 409 and "Choose another supplier" in need.json()["detail"]
    assert client.delete(f"/api/catalog/suppliers/{frz['id']}?move_to={frz['id']}", headers=as_user(owner)).status_code == 422

    done = client.delete(f"/api/catalog/suppliers/{frz['id']}?move_to={dry['id']}", headers=as_user(owner)).json()
    assert done == {"removed": frz["name"], "moved_items": frz["items"], "moved_to": dry["name"]}
    codes = {s["code"]: s for s in client.get("/api/catalog/suppliers", headers=as_user(owner)).json()}
    assert "SUP-FRZ" not in codes and codes["SUP-DRY"]["items"] == dry["items"] + frz["items"]
    assert db.get(Supplier, frz["id"]).active is False  # hidden, not deleted
    assert "supplier_removed" in actions(db)
    assert client.delete(f"/api/catalog/suppliers/{frz['id']}?move_to={dry['id']}", headers=as_user(owner)).status_code == 404


def test_a_removed_supplier_no_longer_gets_orders_and_its_name_can_be_reused(client, users, loaded):
    from tests.test_planning import make_plan

    owner = users["owner"]
    frz, dry = supplier(client, owner, "SUP-FRZ"), supplier(client, owner, "SUP-DRY")
    client.delete(f"/api/catalog/suppliers/{frz['id']}?move_to={dry['id']}", headers=as_user(owner))
    plan = make_plan(client, users, 3)
    assert frz["id"] not in {o["supplier_id"] for o in plan["orders"]}
    assert client.post("/api/catalog/suppliers", json={"name": frz["name"]}, headers=as_user(users["manager"])).status_code == 201
    settings_suppliers = client.get("/api/settings", headers=as_user(owner)).json()["suppliers"]
    assert frz["id"] not in {s["id"] for s in settings_suppliers}
    gone = client.post("/api/inventory/items", json={**NEW_ITEM, "supplier_id": frz["id"]}, headers=as_user(users["manager"]))
    assert gone.status_code == 422


def test_a_supplier_with_an_order_in_progress_cannot_be_removed_but_old_drafts_are_closed(client, db, users, loaded):
    from app.modules.planning.models import PurchaseOrder
    from tests.test_planning import act, make_plan

    owner = users["owner"]
    plan = make_plan(client, users, 3)
    first, second = plan["orders"][0], plan["orders"][1]
    assert act(client, users["manager"], first["id"], "submit").status_code == 200  # now waiting for the owner
    other = supplier(client, owner, "SUP-DRY")["id"]
    blocked = client.delete(f"/api/catalog/suppliers/{first['supplier_id']}?move_to={other}", headers=as_user(owner))
    assert blocked.status_code == 409 and "in progress" in blocked.json()["detail"]

    # a supplier that only has an unsent draft can go; the draft is closed so it cannot be left dangling
    target = second["supplier_id"] if second["supplier_id"] != other else first["supplier_id"]
    ok = client.delete(f"/api/catalog/suppliers/{second['supplier_id']}?move_to={target}", headers=as_user(owner))
    assert ok.status_code == 200, ok.text
    order = db.get(PurchaseOrder, second["id"])
    assert (order.status, order.reject_reason) == ("rejected", "Supplier removed")


def test_old_orders_keep_the_name_of_a_removed_supplier(client, users, loaded):
    from tests.test_planning import make_plan

    owner = users["owner"]
    plan = make_plan(client, users, 3)
    gone = plan["orders"][0]
    others = [s for s in client.get("/api/catalog/suppliers", headers=as_user(owner)).json() if s["id"] != gone["supplier_id"]]
    assert client.delete(f"/api/catalog/suppliers/{gone['supplier_id']}?move_to={others[0]['id']}", headers=as_user(owner)).status_code == 200
    seen = client.get(f"/api/planning/orders/{gone['id']}", headers=as_user(owner)).json()
    assert seen["supplier_name"] == gone["supplier_name"]


# ---------- databases made before the "active" column existed ----------
def test_an_old_database_gets_the_missing_supplier_column():
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.pool import StaticPool

    from app.db import init_db

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as conn:  # a suppliers table as it was before suppliers could be removed
        conn.execute(text("CREATE TABLE suppliers (id INTEGER PRIMARY KEY, tenant_id INTEGER, code VARCHAR(40), name VARCHAR(120), "
                          "category VARCHAR(120), delivery_days VARCHAR(60), lead_time_days INTEGER, min_order_rm FLOAT, whatsapp VARCHAR(30))"))
        conn.execute(text("INSERT INTO suppliers VALUES (1, 1, 'SUP-OLD', 'Old Co', '', 'Daily', 0, 0, '')"))
    init_db(engine)
    init_db(engine)  # running twice must be harmless
    assert "active" in {c["name"] for c in inspect(engine).get_columns("suppliers")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT active FROM suppliers WHERE code='SUP-OLD'")).scalar() in (1, True)
