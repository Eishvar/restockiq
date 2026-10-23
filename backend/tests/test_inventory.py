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


# ---------- batches: the same item bought on different days is tracked separately ----------
def make_item(client, users, **over):
    body = {**NEW_ITEM, "name": "Raw Chicken", "shelf_life_days": 3, "qty_base": 2000, "last_purchased_on": "2026-10-19", **over}
    return client.post("/api/inventory/items", json=body, headers=as_user(users["manager"])).json()


def test_same_item_on_different_days_is_separate_batches_with_own_expiry(client, users, loaded):
    h = as_user(users["manager"])
    chicken = make_item(client, users)  # bought Monday 19 Oct, 3 days: expired on 22 Oct
    assert len(chicken["batches"]) == 1
    r = client.post(f"/api/inventory/{chicken['ingredient_id']}/batches",
                    json={"qty_base": 3000, "procured_on": "2026-10-21", "pack_price_rm": 12.5}, headers=h)
    assert r.status_code == 201
    row = r.json()
    mon, wed = row["batches"]
    assert (mon["procured_on"], mon["expires_on"], mon["status"]) == ("2026-10-19", "2026-10-22", "expired")
    assert (wed["procured_on"], wed["expires_on"], wed["status"]) == ("2026-10-21", "2026-10-24", "expiring_soon")
    assert wed["pack_price_rm"] == 12.5 and mon["pack_price_rm"] == NEW_ITEM["pack_price_rm"]
    assert wed["value_rm"] == round(3000 / NEW_ITEM["pack_size_base"] * 12.5, 2)
    assert row["qty_base"] == 5000 and row["status"] == "expired" and row["expired_qty_base"] == 2000
    assert row["expires_on"] == "2026-10-22"  # the batch that expires first


def test_adding_stock_on_the_same_date_merges_into_one_batch(client, users, loaded):
    h = as_user(users["manager"])
    chicken = make_item(client, users, shelf_life_days=10)
    r = client.post(f"/api/inventory/{chicken['ingredient_id']}/batches",
                    json={"qty_base": 2000, "procured_on": "2026-10-19"}, headers=h).json()
    assert len(r["batches"]) == 1 and r["batches"][0]["qty_base"] == 4000


def test_batch_defaults_and_validation(client, users, loaded):
    h = as_user(users["manager"])
    chicken = make_item(client, users)
    url = f"/api/inventory/{chicken['ingredient_id']}/batches"
    b = client.post(url, json={"qty_base": 500}, headers=h).json()["batches"][-1]
    assert b["procured_on"] == "2026-10-22" and b["shelf_life_days"] == 3 and b["pack_price_rm"] == NEW_ITEM["pack_price_rm"]
    assert client.post(url, json={"qty_base": 500, "procured_on": "2026-12-01"}, headers=h).status_code == 422
    assert client.post(url, json={"qty_base": 0}, headers=h).status_code == 422
    assert client.post(url, json={"qty_base": 5}, headers=as_user(users["staff"])).status_code == 403


def test_discard_only_the_expired_batch(client, db, users, loaded):
    h = as_user(users["manager"])
    chicken = make_item(client, users)
    client.post(f"/api/inventory/{chicken['ingredient_id']}/batches", json={"qty_base": 3000, "procured_on": "2026-10-21"}, headers=h)
    mon, wed = next(
        i for i in client.get("/api/inventory", headers=h).json()["items"] if i["ingredient_id"] == chicken["ingredient_id"]
    )["batches"]
    assert client.post(f"/api/inventory/batches/{wed['id']}/discard", headers=h).status_code == 409  # not expired
    r = client.post(f"/api/inventory/batches/{mon['id']}/discard", headers=as_user(users["staff"]))
    assert r.status_code == 200 and r.json() == {"discarded": ["Raw Chicken"], "batches": 1}
    row = next(i for i in client.get("/api/inventory", headers=h).json()["items"] if i["ingredient_id"] == chicken["ingredient_id"])
    assert [b["id"] for b in row["batches"]] == [wed["id"]] and row["qty_base"] == 3000 and row["status"] == "expiring_soon"
    last = moves(db, chicken["ingredient_id"])[-1]
    assert (last.reason, last.change_base) == ("discard_expired", -2000)
    log = db.scalars(select(ActivityLog).where(ActivityLog.action == "inventory_expired_discarded")).all()[-1]
    assert log.details["procured_on"] == "2026-10-19" and log.details["expired_on"] == "2026-10-22"


def test_discard_all_expired_removes_every_expired_batch(client, users, loaded):
    h = as_user(users["manager"])
    chicken = make_item(client, users)
    client.post(f"/api/inventory/{chicken['ingredient_id']}/batches", json={"qty_base": 1, "procured_on": "2026-10-18"}, headers=h)
    before = client.get("/api/inventory", headers=h).json()["items"]
    n_expired = sum(b["status"] == "expired" for i in before for b in i["batches"])
    r = client.post("/api/inventory/discard-expired", headers=h).json()
    assert r["batches"] == n_expired and "Raw Chicken" in r["discarded"]
    after = client.get("/api/inventory", headers=h).json()["items"]
    assert not [b for i in after for b in i["batches"] if b["status"] == "expired"]


def test_edit_and_remove_a_batch(client, db, users, loaded):
    h = as_user(users["manager"])
    chicken = make_item(client, users, shelf_life_days=30)
    client.post(f"/api/inventory/{chicken['ingredient_id']}/batches", json={"qty_base": 3000, "procured_on": "2026-10-21"}, headers=h)
    mon, wed = next(i for i in client.get("/api/inventory", headers=h).json()["items"] if i["ingredient_id"] == chicken["ingredient_id"])["batches"]
    url = f"/api/inventory/batches/{wed['id']}"
    r = client.patch(url, json={"shelf_life_days": 2, "pack_price_rm": 9}, headers=h)
    assert r.status_code == 200
    got = next(b for b in r.json()["batches"] if b["id"] == wed["id"])
    assert (got["shelf_life_days"], got["pack_price_rm"], got["expires_on"], got["status"]) == (2, 9, "2026-10-23", "expiring_soon")
    assert client.patch(url, json={"procured_on": "2026-10-19"}, headers=h).status_code == 409  # that day already has a batch
    assert client.patch(url, json={"procured_on": "2026-12-01"}, headers=h).status_code == 422
    assert client.patch(url, json={"shelf_life_days": 5}, headers=as_user(users["staff"])).status_code == 403
    assert client.patch(url, json={"qty_base": 100}, headers=as_user(users["staff"])).status_code == 200
    assert client.delete(url, headers=as_user(users["staff"])).status_code == 403
    assert client.delete(url, headers=h).status_code == 204
    row = next(i for i in client.get("/api/inventory", headers=h).json()["items"] if i["ingredient_id"] == chicken["ingredient_id"])
    assert [b["id"] for b in row["batches"]] == [mon["id"]] and row["qty_base"] == 2000
    assert client.patch(url, json={"qty_base": 1}, headers=h).status_code == 404
    actions = [a.action for a in db.scalars(select(ActivityLog).order_by(ActivityLog.id))]
    assert actions[-3:] == ["inventory_batch_edited", "inventory_batch_edited", "inventory_batch_removed"]


def test_item_level_quantity_edit_with_several_batches_uses_oldest_stock_first(client, users, loaded):
    h = as_user(users["manager"])
    chicken = make_item(client, users, shelf_life_days=30)  # 2000 on 19 Oct
    client.post(f"/api/inventory/{chicken['ingredient_id']}/batches", json={"qty_base": 3000, "procured_on": "2026-10-21"}, headers=h)
    r = client.patch(f"/api/inventory/{chicken['ingredient_id']}", json={"qty_base": 2500}, headers=h).json()  # used 2500
    assert [(b["procured_on"], b["qty_base"]) for b in r["batches"]] == [("2026-10-21", 2500)]
    # a date change is ambiguous with several batches
    client.post(f"/api/inventory/{chicken['ingredient_id']}/batches", json={"qty_base": 10, "procured_on": "2026-10-20"}, headers=h)
    assert client.patch(f"/api/inventory/{chicken['ingredient_id']}", json={"last_purchased_on": "2026-10-18"}, headers=h).status_code == 409


def test_stock_saved_before_batches_existed_is_upgraded(client, db, users, loaded):
    from app.modules.inventory.models import InventoryBatch
    from app.modules.inventory.service import backfill_batches

    db.query(InventoryBatch).delete()
    db.commit()
    created = backfill_batches(db)
    assert created > 0 and backfill_batches(db) == 0  # safe to run on every start
    rows = client.get("/api/inventory", headers=as_user(users["staff"])).json()["items"]
    assert all(len(i["batches"]) == (1 if i["qty_base"] > 0 else 0) for i in rows)
    assert all(abs(sum(b["qty_base"] for b in i["batches"]) - i["qty_base"]) < 1e-6 for i in rows)
