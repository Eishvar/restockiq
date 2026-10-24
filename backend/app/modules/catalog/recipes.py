"""Recipes: which ingredients, and how much of each, go into one serving of a dish.

The forecast says how many of each dish will sell; the recipe turns that into ingredients. A dish with no recipe
cannot be turned into ingredients, so first-time setup does not finish until every dish has one. A recipe is saved
whole (all its lines at once), every change is written to the activity log, and the next plan uses the new amounts.
"""
import re

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.activity import log_action
from app.core.clock import now_kl
from app.modules.catalog.models import Ingredient, MenuItem, Recipe
from app.modules.catalog.schemas import DishRecipeOut, RecipeLineIn, RecipeLineOut
from app.modules.catalog.service import _clean
from app.modules.settings.models import User

MAX_DISH_NAME, MAX_CATEGORY = 160, 80


def _fmt(qty: float) -> str:
    return f"{qty:g}"


def _describe(lines: list[RecipeLineOut]) -> str:
    return ", ".join(f"{l.ingredient_name} {_fmt(l.qty_per_serving)} {l.base_uom}" for l in lines) or "no recipe"


def _lines_by_dish(db: Session, tenant_id: int) -> dict[int, list[RecipeLineOut]]:
    stmt = (
        select(Recipe.menu_item_id, Recipe.ingredient_id, Recipe.qty_per_serving, Ingredient.name, Ingredient.base_uom)
        .join(Ingredient, Ingredient.id == Recipe.ingredient_id)
        .where(Recipe.tenant_id == tenant_id, Recipe.status == "approved")
        .order_by(Ingredient.name)
    )
    out: dict[int, list[RecipeLineOut]] = {}
    for dish_id, ing_id, qty, name, uom in db.execute(stmt):
        out.setdefault(dish_id, []).append(
            RecipeLineOut(ingredient_id=ing_id, ingredient_name=name, qty_per_serving=qty, base_uom=uom)
        )
    return out


def _dish_out(dish: MenuItem, lines: list[RecipeLineOut]) -> DishRecipeOut:
    return DishRecipeOut(
        id=dish.id, code=dish.code, name=dish.name, category=dish.category, price_rm=dish.price_rm,
        has_recipe=bool(lines), lines=lines,
    )


def _active_dishes(db: Session, tenant_id: int) -> list[MenuItem]:
    return list(
        db.scalars(select(MenuItem).where(MenuItem.tenant_id == tenant_id, MenuItem.active.is_(True)).order_by(MenuItem.name))
    )


def recipe_book(db: Session, user: User) -> list[DishRecipeOut]:
    """Every dish on the menu with its recipe lines (an empty list when it has none yet)."""
    lines = _lines_by_dish(db, user.tenant_id)
    return [_dish_out(d, lines.get(d.id, [])) for d in _active_dishes(db, user.tenant_id)]


def dishes_without_recipe(db: Session, tenant_id: int) -> list[str]:
    have = _lines_by_dish(db, tenant_id)
    return [d.name for d in _active_dishes(db, tenant_id) if d.id not in have]


def recipes_edited(db: Session, tenant_id: int) -> bool:
    """True once anyone changed a recipe by hand (the safety buffers were measured on the originals)."""
    return db.scalar(select(Recipe.id).where(Recipe.tenant_id == tenant_id, Recipe.source != "seed").limit(1)) is not None


def _checked_lines(db: Session, tenant_id: int, lines: list[RecipeLineIn]) -> list[tuple[Ingredient, float]]:
    if not lines:
        raise HTTPException(422, "A dish needs at least one ingredient.")
    ids = [l.ingredient_id for l in lines]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Each ingredient can only appear once in a recipe. Change its amount instead.")
    found = {
        i.id: i
        for i in db.scalars(
            select(Ingredient).where(Ingredient.tenant_id == tenant_id, Ingredient.active.is_(True), Ingredient.id.in_(ids))
        )
    }
    if len(found) != len(ids):
        raise HTTPException(422, "One of the ingredients does not exist. Add it under Inventory first.")
    return [(found[l.ingredient_id], round(l.qty_per_serving, 4)) for l in lines]


def _write_lines(db: Session, user: User, dish: MenuItem, checked: list[tuple[Ingredient, float]]) -> None:
    db.execute(delete(Recipe).where(Recipe.tenant_id == user.tenant_id, Recipe.menu_item_id == dish.id))
    for ing, qty in checked:
        db.add(Recipe(tenant_id=user.tenant_id, menu_item_id=dish.id, ingredient_id=ing.id, qty_per_serving=qty,
                      status="approved", source="manual"))


def _as_lines(checked: list[tuple[Ingredient, float]]) -> list[RecipeLineOut]:
    return [
        RecipeLineOut(ingredient_id=i.id, ingredient_name=i.name, qty_per_serving=q, base_uom=i.base_uom)
        for i, q in sorted(checked, key=lambda t: t[0].name)
    ]


def save_recipe(db: Session, user: User, menu_item_id: int, lines: list[RecipeLineIn]) -> tuple[DishRecipeOut, bool]:
    """Replace one dish's recipe. Returns the dish and whether anything actually changed."""
    dish = db.scalar(select(MenuItem).where(MenuItem.id == menu_item_id, MenuItem.tenant_id == user.tenant_id))
    if dish is None:
        raise HTTPException(404, "Dish not found")
    checked = _checked_lines(db, user.tenant_id, lines)
    before = _lines_by_dish(db, user.tenant_id).get(dish.id, [])
    after = _as_lines(checked)
    if {(l.ingredient_id, l.qty_per_serving) for l in before} == {(l.ingredient_id, l.qty_per_serving) for l in after}:
        return _dish_out(dish, before), False
    _write_lines(db, user, dish, checked)
    log_action(db, user, "recipe_updated", "menu_item", dish.id,
               {"dish": dish.name, "before": _describe(before), "after": _describe(after)})
    db.commit()
    return _dish_out(dish, after), True


def add_dish(db: Session, user: User, name: str, category: str, price_rm: float, lines: list[RecipeLineIn]) -> DishRecipeOut:
    """Add a new dish with its recipe. Sales files match dishes by name, so names must be unique."""
    name = _clean(name, MAX_DISH_NAME, "dish")
    category = _clean(category, MAX_CATEGORY, "category")
    checked = _checked_lines(db, user.tenant_id, lines)
    everyone = list(db.scalars(select(MenuItem).where(MenuItem.tenant_id == user.tenant_id)))
    if any(m.name.strip().lower() == name.lower() for m in everyone):
        raise HTTPException(409, f"You already have a dish called {name}.")
    taken = {m.code.lower() for m in everyone}
    n = max([int(m.group(1)) for m in (re.fullmatch(r"M(\d+)", c.upper()) for c in taken) if m] or [0]) + 1
    while f"m{n:03d}" in taken:
        n += 1
    dish = MenuItem(tenant_id=user.tenant_id, code=f"M{n:03d}", name=name, category=category, price_rm=round(price_rm, 2),
                    launch_date=now_kl().date(), active=True)
    db.add(dish)
    db.flush()
    _write_lines(db, user, dish, checked)
    log_action(db, user, "dish_added", "menu_item", dish.id,
               {"dish": name, "category": category, "price_rm": dish.price_rm, "recipe": _describe(_as_lines(checked))})
    db.commit()
    return _dish_out(dish, _as_lines(checked))
