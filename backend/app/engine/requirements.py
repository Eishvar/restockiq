"""Dishes -> raw ingredients: need[ingredient, day] = sum over dishes of qty x quantity-per-serving."""
from dataclasses import dataclass

import pandas as pd


@dataclass
class Requirements:
    need: pd.DataFrame  # date, ingredient_id, need_base
    exceptions: list[dict]  # dishes that sell but have no recipe (a human must add one)
    multiplications: int  # how many dish x ingredient x day products were computed


def requirements(dishes: pd.DataFrame, recipes: pd.DataFrame, item_names: dict | None = None) -> Requirements:
    """dishes: date, item_id, qty.  recipes: item_id, ingredient_id, qty_per_serving."""
    recipes = recipes.groupby(["item_id", "ingredient_id"], as_index=False).qty_per_serving.sum()
    with_recipe = set(recipes.item_id)
    missing = dishes[(~dishes.item_id.isin(with_recipe)) & (dishes.qty > 0)]
    exceptions = [
        {
            "type": "dish_without_recipe",
            "item_id": item_id,
            "name": (item_names or {}).get(item_id),
            "expected_qty": round(float(g.qty.sum()), 1),
        }
        for item_id, g in missing.groupby("item_id")
    ]

    joined = dishes.merge(recipes, on="item_id")
    joined["need_base"] = joined.qty * joined.qty_per_serving
    need = joined.groupby(["date", "ingredient_id"], as_index=False).need_base.sum()
    return Requirements(need=need, exceptions=exceptions, multiplications=len(joined))
