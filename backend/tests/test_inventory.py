from datetime import date

import pytest
from sqlalchemy import select

from app.modules.activity.models import ActivityLog
from app.modules.inventory.models import InventoryMovement
from app.modules.inventory.service import compute_status
from tests.conftest import as_user

TODAY = date(2026, 10, 22)


# ---------- status computation (pure) ----------
@pytest.mark.parametrize(
    "bought, shelf, qty, expected",
    [
        (date(2026, 10, 19), 90, 100, ("ok", 87)),
        (date(2026, 10, 10), 14, 100, ("expiring_soon", 2)),  # expires 24 Oct: 2 days left
        (date(2026, 10, 11), 14, 100, ("ok", 3)),  # expires 25 Oct: 3 days left is still ok
        (date(2026, 10, 21), 1, 100, ("expired", 0)),  # expires today
        (date(2026, 10, 1), 7, 100, ("expired", -14)),
        (date(2026, 10, 1), 7, 0, ("ok", -14)),  # nothing on the shelf, nothing to expire
    ],
)
def test_compute_status(bought, shelf, qty, expected):
    _, days_left, status = compute_status(bought, shelf, qty, TODAY)
    assert (status, days_left) == expected


def test_compute_status_without_purchase_date():
    assert compute_status(None, 7, 50, TODAY) == (None, None, "ok")


# ---------- the demo data ----------
def test_demo_shows_expired_and_expiring(client, users, loaded):
    r = client.get("/api/inventory", headers=as_user(users["staff"])).json()
    assert r["today"] == "2026-10-22" and r["onboarded"] is False
    expired = {i["name"] for i in r["items"] if i["status"] == "expired"}
    assert len(expired) == 3 and any("milk" in n.lower() for n in expired)
    soon = [i for i in r["items"] if i["status"] == "expiring_soon"]
    assert any("egg" in i["name"].lower() and i["days_left"] == 2 for i in soon)
    assert all(i["display_qty"] for i in r["items"])


def item(client, user, name_part):
    rows = client.get("/api/inventory", headers=as_user(user)).json()["items"]
    return next(i for i in rows if name_part in i["name"].lower())


def test_editing_shelf_life_changes_status(client, users, loaded):
    h = as_user(users["manager"])
    eggs = item(client, users["manager"], "egg")
    assert eggs["status"] == "expiring_soon"
    r = client.patch(f"/api/inventory/{eggs['ingredient_id']}", json={"shelf_life_days": 60}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "ok"
    r = client.patch(f"/api/inventory/{eggs['ingredient_id']}", json={"shelf_life_days": 1}, headers=h)
    assert r.json()["status"] == "expired"


# ---------- role rules ----------
def test_staff_can_change_quantity_only(client, users, loaded):
    rice = item(client, users["staff"], "rice")
    url, h = f"/api/inventory/{rice['ingredient_id']}", as_user(users["staff"])
    assert client.patch(url, json={"qty_base": 500}, headers=h).json()["qty_base"] == 500
    assert client.patch(url, json={"shelf_life_days": 5}, headers=h).status_code == 403
    assert client.patch(url, json={"last_purchased_on": "2026-10-20"}, headers=h).status_code == 403
    assert client.patch(url, json={"pack_price_rm": 1}, headers=h).status_code == 403


NEW_ITEM = {
    "name": "Kicap manis 2L",
    "storage": "dry",
    "base_uom": "ml",
    "pack_uom": "BTL (2L)",
    "pack_size_base": 2000,
    "pack_price_rm": 9.5,
    "shelf_life_days": 730,
    "qty_base": 4000,
}


def test_add_and_remove_need_manager(client, users, loaded):
    assert client.post("/api/inventory/items", json=NEW_ITEM, headers=as_user(users["staff"])).status_code == 403
    r = client.post("/api/inventory/items", json=NEW_ITEM, headers=as_user(users["manager"]))
    assert r.status_code == 201
    new = r.json()
    assert new["qty_base"] == 4000 and new["status"] == "ok" and new["last_purchased_on"] == "2026-10-22"
    assert client.delete(f"/api/inventory/{new['ingredient_id']}", headers=as_user(users["staff"])).status_code == 403
    assert client.delete(f"/api/inventory/{new['ingredient_id']}", headers=as_user(users["manager"])).status_code == 204
    names = [i["name"] for i in client.get("/api/inventory", headers=as_user(users["owner"])).json()["items"]]
    assert "Kicap manis 2L" not in names  # soft-deleted items are hidden


def test_add_item_validation(client, users, loaded):
    h = as_user(users["manager"])
    assert client.post("/api/inventory/items", json={**NEW_ITEM, "shelf_life_days": 0}, headers=h).status_code == 422
    assert client.post("/api/inventory/items", json={**NEW_ITEM, "supplier_id": 9999}, headers=h).status_code == 422
    assert client.post("/api/inventory/items", json={**NEW_ITEM, "qty_base": -1}, headers=h).status_code == 422


def test_same_name_gets_unique_code(client, users, loaded):
    h = as_user(users["manager"])
    a = client.post("/api/inventory/items", json=NEW_ITEM, headers=h).json()
    b = client.post("/api/inventory/items", json=NEW_ITEM, headers=h).json()
    assert a["code"] != b["code"]


# ---------- movements and activity log ----------
def moves(db, ingredient_id):
    return db.scalars(
        select(InventoryMovement).where(InventoryMovement.ingredient_id == ingredient_id).order_by(InventoryMovement.id)
    ).all()


def test_quantity_edit_writes_movement_and_log_with_before_after(client, db, users, loaded):
    rice = item(client, users["manager"], "rice")
    old = rice["qty_base"]
    client.patch(f"/api/inventory/{rice['ingredient_id']}", json={"qty_base": old + 250}, headers=as_user(users["manager"]))
    last = moves(db, rice["ingredient_id"])[-1]
    assert (last.reason, last.change_base, last.user_id) == ("adjust", 250, users["manager"].id)
    log = db.scalars(select(ActivityLog).where(ActivityLog.action == "inventory_edited")).one()
    assert log.role == "manager" and log.details["before"]["qty_base"] == old and log.details["after"]["qty_base"] == old + 250

    # editing something that doesn't change quantity writes no movement
    n = len(moves(db, rice["ingredient_id"]))
    client.patch(f"/api/inventory/{rice['ingredient_id']}", json={"shelf_life_days": 400}, headers=as_user(users["manager"]))
    assert len(moves(db, rice["ingredient_id"])) == n


def test_unchanged_patch_is_not_logged(client, db, users, loaded):
    rice = item(client, users["manager"], "rice")
    client.patch(f"/api/inventory/{rice['ingredient_id']}", json={"qty_base": rice["qty_base"]}, headers=as_user(users["manager"]))
    assert db.scalars(select(ActivityLog).where(ActivityLog.action == "inventory_edited")).first() is None


def test_future_purchase_date_rejected(client, users, loaded):
    rice = item(client, users["manager"], "rice")
    r = client.patch(f"/api/inventory/{rice['ingredient_id']}", json={"last_purchased_on": "2026-12-01"}, headers=as_user(users["manager"]))
    assert r.status_code == 422


def test_add_remove_movements(client, db, users, loaded):
    new = client.post("/api/inventory/items", json=NEW_ITEM, headers=as_user(users["manager"])).json()
    client.delete(f"/api/inventory/{new['ingredient_id']}", headers=as_user(users["manager"]))
    reasons = [(m.reason, m.change_base) for m in moves(db, new["ingredient_id"])]
    assert reasons == [("onboarding", 4000), ("removed", -4000)]  # not onboarded yet => onboarding
    actions = [a.action for a in db.scalars(select(ActivityLog).order_by(ActivityLog.id))]
    assert actions == ["inventory_item_added", "inventory_item_removed"]


# ---------- discarding expired stock ----------
def test_discard_expired_one_and_all(client, db, users, loaded):
    h = as_user(users["staff"])  # any signed-in user may throw away expired stock
    rows = client.get("/api/inventory", headers=h).json()["items"]
    expired = [i for i in rows if i["status"] == "expired"]
    ok_item = next(i for i in rows if i["status"] == "ok")
    assert client.post(f"/api/inventory/{ok_item['ingredient_id']}/discard-expired", headers=h).status_code == 409

    first = expired[0]
    r = client.post(f"/api/inventory/{first['ingredient_id']}/discard-expired", headers=h)
    assert r.status_code == 200 and r.json()["discarded"] == [first["name"]]
    last = moves(db, first["ingredient_id"])[-1]
    assert (last.reason, last.change_base) == ("discard_expired", -first["qty_base"])

    r = client.post("/api/inventory/discard-expired", headers=h)
    assert len(r.json()["discarded"]) == len(expired) - 1
    after = client.get("/api/inventory", headers=h).json()["items"]
    assert not [i for i in after if i["status"] == "expired"]
    logged = db.scalars(select(ActivityLog).where(ActivityLog.action == "inventory_expired_discarded")).all()
    assert len(logged) == len(expired)


def test_movement_history_endpoint(client, users, loaded):
    rice = item(client, users["staff"], "rice")
    client.patch(f"/api/inventory/{rice['ingredient_id']}", json={"qty_base": rice["qty_base"] - 100}, headers=as_user(users["staff"]))
    hist = client.get(f"/api/inventory/{rice['ingredient_id']}/movements", headers=as_user(users["staff"])).json()
    assert [h["reason"] for h in hist] == ["adjust", "onboarding"]
    assert hist[0]["user_name"] == users["staff"].name and hist[0]["display_change"].startswith("-")


# ---------- onboarding ----------
def test_onboarding_confirm_is_owner_only_and_logged_once(client, db, users, loaded):
    assert client.post("/api/inventory/onboarding/confirm", headers=as_user(users["manager"])).status_code == 403
    r = client.post("/api/inventory/onboarding/confirm", headers=as_user(users["owner"]))
    assert r.status_code == 200 and r.json()["onboarded"] is True
    client.post("/api/inventory/onboarding/confirm", headers=as_user(users["owner"]))  # idempotent
    assert client.get("/api/inventory", headers=as_user(users["staff"])).json()["onboarded"] is True
    logs = db.scalars(select(ActivityLog).where(ActivityLog.action == "onboarding_confirmed")).all()
    assert len(logs) == 1 and logs[0].details["items"] == 74


def test_new_item_after_onboarding_is_an_adjustment(client, db, users, loaded):
    client.post("/api/inventory/onboarding/confirm", headers=as_user(users["owner"]))
    new = client.post("/api/inventory/items", json=NEW_ITEM, headers=as_user(users["manager"])).json()
    assert moves(db, new["ingredient_id"])[0].reason == "adjust"


def test_inventory_requires_login(client, loaded):
    assert client.get("/api/inventory").status_code == 401
