"""Recipes: view, edit and add dishes, the mandatory setup step, and that the plan reads the edited amounts."""
from datetime import datetime

import pytest
from sqlalchemy import create_engine, inspect, select, text

from app.db import init_db
from app.modules.activity.models import ActivityLog
from app.modules.catalog.models import Ingredient, MenuItem, Recipe
from app.modules.planning import refresh
from app.modules.planning.data import load_frames
from app.modules.settings.models import Tenant
from app.modules.setup.models import TenantSetup
from tests.conftest import as_user


@pytest.fixture()
def background(monkeypatch):
    calls = []
    monkeypatch.setattr(refresh, "run_recompute", lambda tenant_id, user_id, trigger: calls.append(trigger))
    return calls


def actions(db):
    return [a.action for a in db.scalars(select(ActivityLog).order_by(ActivityLog.id))]


def book(client, user):
    r = client.get("/api/catalog/recipe-book", headers=as_user(user))
    assert r.status_code == 200, r.text
    return r.json()


def finish_setup(db, tenant_id=1):
    row = db.get(TenantSetup, tenant_id) or TenantSetup(tenant_id=tenant_id)
    row.setup_done_at = row.recipes_confirmed_at = datetime(2026, 10, 1)
    db.add(row)
    db.commit()


def two_ingredients(db):
    return list(db.scalars(select(Ingredient).where(Ingredient.active.is_(True)).order_by(Ingredient.id).limit(2)))


# ---------- view ----------
def test_recipe_book_lists_every_dish_with_its_ingredients(client, users, loaded):
    dishes = book(client, users["staff"])  # everyone can read
    assert len(dishes) == loaded["menu_items"] and all(d["has_recipe"] for d in dishes)
    rice = next(d for d in dishes if d["name"] == "White rice")
    assert [(l["qty_per_serving"], l["base_uom"]) for l in rice["lines"]] == [(90.0, "g")]  # 90 g per serving, from recipes.csv
    assert client.get("/api/catalog/recipe-book").status_code == 401


# ---------- edit ----------
def test_manager_edits_a_recipe_and_the_change_is_logged(client, db, users, loaded, background):
    finish_setup(db)
    dish = db.scalar(select(MenuItem).where(MenuItem.name == "White rice"))
    a, b = two_ingredients(db)
    url = f"/api/catalog/menu/{dish.id}/recipe"
    body = {"lines": [{"ingredient_id": a.id, "qty_per_serving": 120}, {"ingredient_id": b.id, "qty_per_serving": 2.5}]}

    r = client.put(url, json=body, headers=as_user(users["manager"]))
    assert r.status_code == 200, r.text
    assert {(l["ingredient_id"], l["qty_per_serving"]) for l in r.json()["lines"]} == {(a.id, 120.0), (b.id, 2.5)}
    rows = list(db.scalars(select(Recipe).where(Recipe.menu_item_id == dish.id)))
    assert len(rows) == 2 and {x.source for x in rows} == {"manual"} and {x.status for x in rows} == {"approved"}
    assert actions(db).count("recipe_updated") == 1 and background == ["recipe"]

    # Saving the same recipe again changes nothing: no second log entry, no second re-measure.
    assert client.put(url, json=body, headers=as_user(users["manager"])).status_code == 200
    assert actions(db).count("recipe_updated") == 1 and background == ["recipe"]
    assert book(client, users["staff"])  # still readable


def test_only_managers_edit_and_bad_recipes_are_refused(client, db, users, loaded, background):
    dish = db.scalar(select(MenuItem).where(MenuItem.name == "White rice"))
    a, b = two_ingredients(db)
    url = f"/api/catalog/menu/{dish.id}/recipe"
    ok = {"lines": [{"ingredient_id": a.id, "qty_per_serving": 50}]}
    assert client.put(url, json=ok, headers=as_user(users["staff"])).status_code == 403
    assert client.put(url, json=ok).status_code == 401

    def put(lines):
        return client.put(url, json={"lines": lines}, headers=as_user(users["manager"])).status_code

    assert put([]) == 422  # a dish needs an ingredient
    assert put([{"ingredient_id": a.id, "qty_per_serving": 0}]) == 422
    assert put([{"ingredient_id": a.id, "qty_per_serving": -5}]) == 422
    assert put([{"ingredient_id": a.id, "qty_per_serving": 1}, {"ingredient_id": a.id, "qty_per_serving": 2}]) == 422  # twice
    assert put([{"ingredient_id": 999999, "qty_per_serving": 1}]) == 422
    assert client.put("/api/catalog/menu/999999/recipe", json=ok, headers=as_user(users["manager"])).status_code == 404
    assert b.id and "recipe_updated" not in actions(db)  # nothing above changed anything


def test_edit_during_setup_waits_for_the_confirm_step_to_remeasure_buffers(client, db, users, loaded, background):
    dish = db.scalar(select(MenuItem).where(MenuItem.name == "White rice"))
    a, _ = two_ingredients(db)
    r = client.put(f"/api/catalog/menu/{dish.id}/recipe", json={"lines": [{"ingredient_id": a.id, "qty_per_serving": 77}]},
                   headers=as_user(users["owner"]))
    assert r.status_code == 200 and background == []  # not after every edit while the wizard is open


def test_the_plan_reads_the_edited_amount(client, db, users, loaded, background):
    dish = db.scalar(select(MenuItem).where(MenuItem.name == "White rice"))
    a, _ = two_ingredients(db)
    client.put(f"/api/catalog/menu/{dish.id}/recipe", json={"lines": [{"ingredient_id": a.id, "qty_per_serving": 123.5}]},
               headers=as_user(users["manager"]))
    recipes = load_frames(db, 1)["recipes"]
    mine = recipes[recipes.item_id == dish.id]
    assert list(zip(mine.ingredient_id, mine.qty_per_serving)) == [(a.id, 123.5)]


# ---------- add a dish ----------
def test_add_a_dish_with_a_recipe(client, db, users, loaded, background):
    a, b = two_ingredients(db)
    body = {"name": "  Nasi   Lemak Special ", "category": "Rice", "price_rm": 7.5,
            "lines": [{"ingredient_id": a.id, "qty_per_serving": 100}, {"ingredient_id": b.id, "qty_per_serving": 1}]}
    assert client.post("/api/catalog/menu", json=body, headers=as_user(users["staff"])).status_code == 403
    r = client.post("/api/catalog/menu", json=body, headers=as_user(users["manager"]))
    assert r.status_code == 201, r.text
    new = r.json()
    assert new["name"] == "Nasi Lemak Special" and new["has_recipe"] and len(new["lines"]) == 2
    assert new["code"] not in {m.code for m in db.scalars(select(MenuItem)) if m.id != new["id"]}
    assert any(d["id"] == new["id"] for d in book(client, users["staff"]))
    assert db.get(MenuItem, new["id"]).launch_date is not None and "dish_added" in actions(db)

    # Names must be unique (sales files match dishes by name), ignoring capitals.
    body["name"] = "nasi lemak special"
    assert client.post("/api/catalog/menu", json=body, headers=as_user(users["manager"])).status_code == 409
    assert client.post("/api/catalog/menu", json={**body, "name": "Other", "lines": []}, headers=as_user(users["manager"])).status_code == 422
    assert client.post("/api/catalog/menu", json={**body, "name": " "}, headers=as_user(users["manager"])).status_code == 422
    assert client.post("/api/catalog/menu", json={**body, "name": "Cheap", "price_rm": -1}, headers=as_user(users["manager"])).status_code == 422


def test_a_new_dish_without_sales_does_not_break_the_plan(client, db, users, loaded):
    a, _ = two_ingredients(db)
    client.post("/api/catalog/menu", json={"name": "Brand new dish", "category": "Rice", "price_rm": 5,
                                           "lines": [{"ingredient_id": a.id, "qty_per_serving": 10}]},
                headers=as_user(users["manager"]))
    r = client.post("/api/planning/plans", json={"horizon_days": 3}, headers=as_user(users["manager"]))
    assert r.status_code in (200, 201), r.text


# ---------- the mandatory setup step ----------
def reach_recipes_step(client, users):
    owner = users["owner"]
    client.post("/api/setup/country", json={"country": "MY"}, headers=as_user(owner))
    client.post("/api/inventory/onboarding/confirm", headers=as_user(owner))
    return owner


def test_setup_cannot_continue_while_a_dish_has_no_recipe(client, db, users, loaded, background):
    owner = reach_recipes_step(client, users)
    dish = db.scalar(select(MenuItem).where(MenuItem.name == "White rice"))
    old = list(db.scalars(select(Recipe).where(Recipe.menu_item_id == dish.id)))
    for row in old:
        db.delete(row)
    db.commit()

    status = client.get("/api/setup/status", headers=as_user(owner)).json()
    assert (status["step"], status["recipes_done"]) == ("recipes", False)
    refused = client.post("/api/setup/recipes/confirm", headers=as_user(owner))
    assert refused.status_code == 409 and "White rice" in refused.json()["detail"]
    assert client.post("/api/setup/complete", json={"skip_calendar": True}, headers=as_user(owner)).status_code == 409

    # Give the dish a recipe by hand: now the step can be confirmed, and the buffers are re-measured once.
    a, _ = two_ingredients(db)
    client.put(f"/api/catalog/menu/{dish.id}/recipe", json={"lines": [{"ingredient_id": a.id, "qty_per_serving": 90}]},
               headers=as_user(owner))
    done = client.post("/api/setup/recipes/confirm", headers=as_user(owner)).json()
    assert (done["step"], done["recipes_done"]) == ("calendar", True)
    assert background == ["recipes"] and "setup_recipes_confirmed" in actions(db)
    client.post("/api/setup/recipes/confirm", headers=as_user(owner))  # confirming twice is harmless
    assert background == ["recipes"] and actions(db).count("setup_recipes_confirmed") == 1


def test_only_the_owner_confirms_and_untouched_recipes_need_no_remeasure(client, db, users, loaded, background):
    owner = reach_recipes_step(client, users)
    assert client.post("/api/setup/recipes/confirm", headers=as_user(users["manager"])).status_code == 403
    assert client.post("/api/setup/recipes/confirm", headers=as_user(owner)).json()["step"] == "calendar"
    assert background == []  # the demo recipes were not edited, so the buffers already match


def test_a_business_that_finished_setup_earlier_is_not_sent_back(client, db, users, loaded):
    db.add(TenantSetup(tenant_id=1, country="MY", currency="MYR", setup_done_at=datetime(2026, 10, 1)))
    db.get(Tenant, 1).onboarded_at = datetime(2026, 10, 1)
    db.commit()
    status = client.get("/api/setup/status", headers=as_user(users["owner"])).json()
    assert (status["step"], status["complete"], status["recipes_done"]) == ("done", True, True)


# ---------- existing databases ----------
def test_init_db_adds_the_new_column_to_an_existing_tenant_setup_table():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE tenant_setup (tenant_id INTEGER PRIMARY KEY, country VARCHAR(2), currency VARCHAR(3), "
                          "pos_provider VARCHAR(30), pos_connected_at DATETIME, calendar_skipped BOOLEAN, setup_done_at DATETIME)"))
    init_db(engine)
    assert "recipes_confirmed_at" in {c["name"] for c in inspect(engine).get_columns("tenant_setup")}
