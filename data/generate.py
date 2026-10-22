"""Synthetic dataset for a campus kopitiam next to AIMST University (Bedong, Kedah).

Inputs : menu_profile.csv (menu names, prices, popularity shares; already synthetic)
Outputs: daily_sales.csv, menu_items.csv, suppliers.csv, ingredients.csv, recipes.csv,
         inventory.csv, calendar_events.csv, daily_totals.png
All numbers are generated; no real transaction is reproduced. Fixed seed => reproducible.

Run: python generate.py
"""
import csv
from datetime import date, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
START, DAYS = date(2025, 10, 22), 365          # 2025-10-22 .. 2026-10-21
BASE_ITEMS_PER_DAY = 315                        # average items sold on a normal semester day
DISPERSION = 6                                  # negative-binomial k (smaller = noisier)
rng = np.random.default_rng(42)
D = date.fromisoformat

# --------------------------------------------------------------------------------------------
# Suppliers and raw items (prices modelled on typical northern-Malaysia wholesale, synthetic)
# --------------------------------------------------------------------------------------------
SUPPLIERS = [
    # id, name, category, delivery_days, lead_time_days, min_order_rm, whatsapp (fake)
    ("SUP-FRZ", "Utara Frozen Supply", "Frozen & chilled", "Mon,Thu", 1, 150, "+60100000001"),
    ("SUP-DRY", "Sinar Borong Dry Goods", "Dry goods & beverage", "Mon,Tue,Wed,Thu,Fri,Sat", 1, 100, "+60100000002"),
    ("SUP-FRS", "Pasar Borong Fresh Produce", "Fresh produce, bakery & ice", "Daily", 0, 0, "+60100000003"),
]

# id, name, supplier, storage, base_uom, pack_uom, pack_size_base, pack_price_rm, shelf_life_days, waste_pct
INGREDIENTS = [
    ("CHICKEN_BREAST", "Boneless chicken breast", "SUP-FRZ", "freezer", "g", "CTN (6x2kg)", 12000, 132.00, 90, 0.03),
    ("CHICKEN_CHOP", "Chicken chop, marinated", "SUP-FRZ", "freezer", "pcs", "CTN (54 pcs)", 54, 205.00, 90, 0.02),
    ("TILAPIA", "Tilapia fillet", "SUP-FRZ", "freezer", "g", "CTN (10kg)", 10000, 75.00, 90, 0.03),
    ("SHRIMP", "Shrimp meat 31/40", "SUP-FRZ", "freezer", "g", "PKT (1kg)", 1000, 14.10, 90, 0.03),
    ("SHOESTRING", "Shoestring fries 7mm", "SUP-FRZ", "freezer", "g", "PKT (2kg)", 2000, 20.15, 365, 0.02),
    ("CURLY_FRIES", "Curly fries", "SUP-FRZ", "freezer", "g", "PKT (700g)", 700, 10.90, 365, 0.02),
    ("WAFFLE_FRIES", "Waffle fries", "SUP-FRZ", "freezer", "g", "PKT (700g)", 700, 12.00, 365, 0.02),
    ("NUGGET", "Chicken nugget tempura", "SUP-FRZ", "freezer", "g", "PKT (1kg)", 1000, 14.95, 180, 0.02),
    ("POPCORN_CHICKEN", "Popcorn chicken", "SUP-FRZ", "freezer", "g", "PKT (1kg)", 1000, 16.90, 180, 0.02),
    ("HOTDOG", "Chicken hotdog", "SUP-FRZ", "freezer", "pcs", "PKT (30 pcs)", 30, 10.00, 90, 0.01),
    ("ONION_RING", "Crumbed onion ring", "SUP-FRZ", "freezer", "g", "PKT (400g)", 400, 7.80, 180, 0.02),
    ("FISH_FINGER", "Fish finger", "SUP-FRZ", "freezer", "pcs", "PKT (20 pcs)", 20, 12.50, 180, 0.01),
    ("WANTON", "Seafood wanton", "SUP-FRZ", "freezer", "pcs", "PKT (50 pcs)", 50, 16.50, 90, 0.02),
    ("PANDAN_CHICKEN", "Pandan chicken", "SUP-FRZ", "freezer", "pcs", "PKT (30 pcs)", 30, 19.10, 90, 0.02),
    ("MANTOU", "Mini mantou", "SUP-FRZ", "freezer", "pcs", "PKT (20 pcs)", 20, 4.80, 180, 0.02),
    ("PRAWN_ROLL", "Prawn roll", "SUP-FRZ", "freezer", "pcs", "PKT (20 pcs)", 20, 15.00, 180, 0.02),
    ("ICE_CREAM", "Vanilla ice cream", "SUP-FRZ", "freezer", "ml", "TUB (4L)", 4000, 38.00, 180, 0.03),
    ("EGG", "Egg grade B", "SUP-FRZ", "chiller", "pcs", "TRAY (30 pcs)", 30, 12.80, 14, 0.02),
    ("MUSHROOM", "Button mushroom, canned", "SUP-FRZ", "dry", "g", "CTN (24x425g)", 10200, 79.20, 730, 0.01),
    ("SPAGHETTI", "Spaghetti", "SUP-FRZ", "dry", "g", "CTN (20x400g)", 8000, 65.00, 365, 0.01),
    ("TERIYAKI", "Teriyaki sauce", "SUP-FRZ", "dry", "ml", "BTL (1.8L)", 1800, 38.50, 365, 0.01),
    ("SWEET_CHILI", "Sweet chili sauce", "SUP-FRZ", "dry", "g", "BTL (980g)", 980, 9.20, 365, 0.01),
    ("RICE", "White rice", "SUP-DRY", "dry", "g", "BAG (10kg)", 10000, 32.00, 365, 0.02),
    ("COOKING_OIL", "Cooking oil", "SUP-DRY", "dry", "g", "TIN (17kg)", 17000, 98.00, 365, 0.00),
    ("SUGAR", "Fine sugar", "SUP-DRY", "dry", "g", "BAG (10x1kg)", 10000, 28.50, 730, 0.00),
    ("WAFFLE_MIX", "Waffle premix", "SUP-DRY", "dry", "g", "PKT (1kg)", 1000, 9.50, 180, 0.02),
    ("DARK_SOY", "Dark soy sauce", "SUP-DRY", "dry", "ml", "BTL (2L)", 2000, 12.00, 730, 0.00),
    ("OYSTER_SAUCE", "Oyster sauce", "SUP-DRY", "dry", "g", "BTL (2.2kg)", 2200, 22.00, 365, 0.00),
    ("TOMYAM_PASTE", "Tomyam paste", "SUP-DRY", "dry", "g", "TUB (1kg)", 1000, 18.00, 365, 0.01),
    ("SAMBAL_PASTE", "Sambal chili paste", "SUP-DRY", "chiller", "g", "TUB (1kg)", 1000, 12.00, 30, 0.02),
    ("SALTED_EGG_POWDER", "Salted egg yolk powder", "SUP-DRY", "dry", "g", "PKT (500g)", 500, 28.00, 180, 0.01),
    ("COOKING_CREAM", "Cooking cream", "SUP-DRY", "chiller", "ml", "BOX (1L)", 1000, 14.00, 90, 0.03),
    ("TOMATO_SAUCE", "Tomato sauce", "SUP-DRY", "dry", "g", "CAN (3.3kg)", 3300, 15.00, 365, 0.01),
    ("SEAWEED", "Dried seaweed", "SUP-DRY", "dry", "g", "PKT (50g)", 50, 6.00, 365, 0.00),
    ("CONDENSED_MILK", "Sweetened condensed milk", "SUP-DRY", "dry", "g", "TRAY (12x500g)", 6000, 48.00, 365, 0.01),
    ("FRESH_MILK", "Fresh milk", "SUP-DRY", "chiller", "ml", "BTL (2L)", 2000, 13.50, 7, 0.03),
    ("MILO", "Milo powder", "SUP-DRY", "dry", "g", "PKT (2kg)", 2000, 42.00, 365, 0.00),
    ("TEA_DUST", "Tea dust", "SUP-DRY", "dry", "g", "PKT (1kg)", 1000, 22.00, 365, 0.00),
    ("COFFEE_POWDER", "Kopi powder", "SUP-DRY", "dry", "g", "PKT (1kg)", 1000, 26.00, 180, 0.00),
    ("WHITE_COFFEE", "White coffee powder", "SUP-DRY", "dry", "g", "PKT (1kg)", 1000, 30.00, 180, 0.00),
    ("GREEN_TEA_POWDER", "Green tea powder", "SUP-DRY", "dry", "g", "PKT (1kg)", 1000, 35.00, 365, 0.00),
    ("ROSE_SYRUP", "Rose syrup", "SUP-DRY", "dry", "ml", "BTL (2L)", 2000, 9.00, 365, 0.00),
    ("RIBENA", "Blackcurrant cordial", "SUP-DRY", "dry", "ml", "BTL (1L)", 1000, 15.00, 365, 0.00),
    ("HONEY", "Honey", "SUP-DRY", "dry", "g", "BTL (1kg)", 1000, 25.00, 730, 0.00),
    ("SOUR_PLUM", "Dried sour plum", "SUP-DRY", "dry", "g", "PKT (500g)", 500, 12.00, 365, 0.00),
    ("LYCHEE", "Lychee in syrup", "SUP-DRY", "dry", "g", "TIN (565g)", 565, 6.50, 730, 0.02),
    ("BLENDED_PREMIX", "Ice-blended premix", "SUP-DRY", "dry", "g", "PKT (1kg)", 1000, 28.00, 365, 0.00),
    ("CHOCOLATE_POWDER", "Chocolate powder", "SUP-DRY", "dry", "g", "PKT (1kg)", 1000, 24.00, 365, 0.00),
    ("OREO", "Cookie crumbs", "SUP-DRY", "dry", "g", "PKT (1kg)", 1000, 25.00, 180, 0.00),
    ("PISTACHIO_PASTE", "Pistachio paste", "SUP-DRY", "dry", "g", "TUB (1kg)", 1000, 65.00, 180, 0.01),
    ("STRAWBERRY_SYRUP", "Strawberry syrup", "SUP-DRY", "dry", "ml", "BTL (1L)", 1000, 18.00, 365, 0.00),
    ("CHICKEN_LEG", "Fresh chicken leg", "SUP-FRS", "chiller", "g", "KG", 1000, 10.50, 2, 0.04),
    ("YELLOW_NOODLES", "Yellow noodles", "SUP-FRS", "chiller", "g", "PKT (1kg)", 1000, 4.50, 3, 0.04),
    ("KANGKUNG", "Kangkung", "SUP-FRS", "chiller", "g", "KG", 1000, 5.00, 2, 0.08),
    ("MIXED_VEG", "Mixed vegetables", "SUP-FRS", "chiller", "g", "KG", 1000, 4.50, 4, 0.08),
    ("ONION", "Big onion", "SUP-FRS", "dry", "g", "KG", 1000, 4.80, 30, 0.03),
    ("GARLIC", "Garlic", "SUP-FRS", "dry", "g", "KG", 1000, 9.00, 60, 0.03),
    ("CHILI", "Fresh red chili", "SUP-FRS", "chiller", "g", "KG", 1000, 16.00, 7, 0.05),
    ("LIME", "Calamansi lime", "SUP-FRS", "chiller", "g", "KG", 1000, 8.00, 10, 0.05),
    ("LEMON", "Lemon", "SUP-FRS", "chiller", "g", "KG", 1000, 10.00, 14, 0.04),
    ("CARROT", "Carrot", "SUP-FRS", "chiller", "g", "KG", 1000, 4.00, 14, 0.04),
    ("TOMATO", "Tomato", "SUP-FRS", "chiller", "g", "KG", 1000, 5.50, 7, 0.05),
    ("WATERMELON", "Watermelon", "SUP-FRS", "chiller", "g", "KG", 1000, 2.20, 5, 0.08),
    ("ORANGE", "Orange", "SUP-FRS", "chiller", "g", "KG", 1000, 7.00, 14, 0.04),
    ("APPLE", "Green apple", "SUP-FRS", "chiller", "g", "KG", 1000, 8.00, 21, 0.03),
    ("HONEYDEW", "Honeydew", "SUP-FRS", "chiller", "g", "KG", 1000, 4.50, 6, 0.08),
    ("PINEAPPLE", "Pineapple", "SUP-FRS", "chiller", "g", "KG", 1000, 4.00, 5, 0.08),
    ("MANGO", "Mango", "SUP-FRS", "chiller", "g", "KG", 1000, 9.00, 5, 0.08),
    ("DRAGON_FRUIT", "Dragon fruit", "SUP-FRS", "chiller", "g", "KG", 1000, 8.00, 7, 0.06),
    ("JAMBU", "Jambu air", "SUP-FRS", "chiller", "g", "KG", 1000, 8.00, 4, 0.08),
    ("AVOCADO", "Avocado", "SUP-FRS", "chiller", "g", "KG", 1000, 14.00, 5, 0.08),
    ("COCONUT", "Young coconut", "SUP-FRS", "chiller", "pcs", "PCS", 1, 3.50, 5, 0.05),
    ("BREAD", "White bread (sliced)", "SUP-FRS", "dry", "pcs", "LOAF (14 slices)", 14, 4.20, 4, 0.05),
    ("ICE", "Ice cubes", "SUP-FRS", "freezer", "g", "BAG (6kg)", 6000, 3.50, 1, 0.05),
]
ING_IDS = {i[0] for i in INGREDIENTS}

# --------------------------------------------------------------------------------------------
# Recipes (per serving, base units) built from menu names
# --------------------------------------------------------------------------------------------
SAUCES = [  # keyword -> extra ingredients
    ("Sambal", {"SAMBAL_PASTE": 30, "ONION": 15}),
    ("Creamy", {"COOKING_CREAM": 40}),
    ("Salted Egg", {"SALTED_EGG_POWDER": 15, "COOKING_CREAM": 15}),
    ("Mushroom", {"MUSHROOM": 40, "COOKING_CREAM": 20}),
    ("Sweet Sour", {"TOMATO_SAUCE": 30, "ONION": 15, "PINEAPPLE": 20}),
    ("Black Sauce", {"DARK_SOY": 15, "OYSTER_SAUCE": 10}),
    ("Thai", {"SWEET_CHILI": 30}),
    ("Teriyaki", {"TERIYAKI": 25}),
]
RICE_PLATE = {"RICE": 90}
FRIED_RICE = {"RICE": 100, "EGG": 1, "COOKING_OIL": 15, "ONION": 10, "GARLIC": 5}
NOODLE_BASE = {"YELLOW_NOODLES": 180, "EGG": 1, "COOKING_OIL": 15, "MIXED_VEG": 30}
PASTA_SAUCE = {
    "Carbonara": {"COOKING_CREAM": 80, "MUSHROOM": 20, "CHICKEN_BREAST": 40},
    "Tomyam": {"TOMYAM_PASTE": 25, "SHRIMP": 30, "CHICKEN_BREAST": 30, "COOKING_CREAM": 30},
    "Bolognese": {"TOMATO_SAUCE": 80, "CHICKEN_BREAST": 50, "ONION": 15},
    "Aglio-Olio": {"GARLIC": 15, "COOKING_OIL": 20, "CHILI": 5, "SHRIMP": 30},
    "Salted Egg": {"SALTED_EGG_POWDER": 20, "COOKING_CREAM": 30, "CHICKEN_BREAST": 40},
}
SNACKS = {
    "French Fries": {"SHOESTRING": 180}, "Curly Fries": {"CURLY_FRIES": 180},
    "Waffle Fries": {"WAFFLE_FRIES": 180}, "Chicken Nugget": {"NUGGET": 150},
    "Chicken Popcorn": {"POPCORN_CHICKEN": 150}, "Fried Sausage": {"HOTDOG": 6},
    "Onion Ring": {"ONION_RING": 150}, "Pandan Chicken": {"PANDAN_CHICKEN": 6},
    "Fried Wanton": {"WANTON": 6}, "Fried Mantou": {"MANTOU": 6, "CONDENSED_MILK": 20},
    "Fish Finger": {"FISH_FINGER": 6}, "Prawn Roll": {"PRAWN_ROLL": 6},
}
FRUIT = {"WATERMELON": "WATERMELON", "MANGO": "MANGO", "JAMBU": "JAMBU", "DRAGON FRUIT": "DRAGON_FRUIT",
         "Honeydew": "HONEYDEW", "PINEAPPLE": "PINEAPPLE"}
DRINKS = [  # first keyword match wins, so specific names come first
    ("Teh O Limau", {"TEA_DUST": 10, "SUGAR": 15, "LIME": 15}),
    ("Teh O", {"TEA_DUST": 10, "SUGAR": 15}),
    ("Green Tea Blended", {"GREEN_TEA_POWDER": 20, "BLENDED_PREMIX": 20, "FRESH_MILK": 100}),
    ("Green Tea", {"GREEN_TEA_POWDER": 15, "SUGAR": 15}),
    ("Milo Blended", {"MILO": 40, "CONDENSED_MILK": 25, "BLENDED_PREMIX": 20}),
    ("Milo", {"MILO": 30, "CONDENSED_MILK": 20}),
    ("Milk Tea", {"TEA_DUST": 10, "CONDENSED_MILK": 30}),
    ("White Coffee", {"WHITE_COFFEE": 25, "CONDENSED_MILK": 20}),
    ("Kopi O", {"COFFEE_POWDER": 12, "SUGAR": 15}),
    ("Kopi", {"COFFEE_POWDER": 12, "CONDENSED_MILK": 25}),
    ("Nescafe", {"COFFEE_POWDER": 8, "CONDENSED_MILK": 20}),
    ("Honey Lemon", {"HONEY": 25, "LEMON": 30}),
    ("Lemon Tea", {"TEA_DUST": 10, "SUGAR": 15, "LEMON": 30}),
    ("Lemon Ribena", {"RIBENA": 30, "LEMON": 30}),
    ("Ribena Lychee", {"RIBENA": 30, "LYCHEE": 60}),
    ("Lemon Ice", {"LEMON": 40, "SUGAR": 15}),
    ("Limau", {"LIME": 30, "SUGAR": 15}),
    ("Watermelon", {"WATERMELON": 350, "SUGAR": 10}),
    ("Orange Carrot", {"ORANGE": 250, "CARROT": 150}),
    ("Orange", {"ORANGE": 450}),
    ("Apple", {"APPLE": 350, "SUGAR": 10}),
    ("Carrot Milk", {"CARROT": 200, "FRESH_MILK": 100, "CONDENSED_MILK": 15}),
    ("Honeydew Blended", {"HONEYDEW": 200, "BLENDED_PREMIX": 20, "FRESH_MILK": 80}),
    ("Honeydew", {"HONEYDEW": 350, "SUGAR": 10}),
    ("Pineapple", {"PINEAPPLE": 350, "SUGAR": 10}),
    ("Bandung", {"ROSE_SYRUP": 30, "CONDENSED_MILK": 30}),
    ("Sirap", {"ROSE_SYRUP": 35}),
    ("Sour Plum", {"SOUR_PLUM": 15, "LIME": 15, "SUGAR": 15}),
    ("Mango", {"MANGO": 200, "FRESH_MILK": 100, "BLENDED_PREMIX": 20}),
    ("Avocado", {"AVOCADO": 150, "FRESH_MILK": 150, "CONDENSED_MILK": 20}),
    ("Coconut Blended", {"COCONUT": 1, "BLENDED_PREMIX": 20, "FRESH_MILK": 80}),
    ("Coconut", {"COCONUT": 1}),
    ("Chocolate Ice", {"CHOCOLATE_POWDER": 30, "BLENDED_PREMIX": 20, "FRESH_MILK": 100}),
    ("Oreo", {"OREO": 30, "BLENDED_PREMIX": 20, "FRESH_MILK": 100}),
    ("Cappucino", {"COFFEE_POWDER": 10, "CHOCOLATE_POWDER": 5, "BLENDED_PREMIX": 20, "FRESH_MILK": 100}),
    ("Mocha", {"COFFEE_POWDER": 8, "CHOCOLATE_POWDER": 20, "BLENDED_PREMIX": 20, "FRESH_MILK": 100}),
    ("Pistachio", {"PISTACHIO_PASTE": 25, "BLENDED_PREMIX": 20, "FRESH_MILK": 100}),
    ("Strawberry", {"STRAWBERRY_SYRUP": 30, "BLENDED_PREMIX": 20, "FRESH_MILK": 100}),
    ("Full Cream", {"FRESH_MILK": 200, "BLENDED_PREMIX": 25, "CONDENSED_MILK": 15}),
]


def add(recipe: dict, extra: dict, scale: float = 1.0) -> dict:
    for k, v in extra.items():
        recipe[k] = recipe.get(k, 0) + v * scale
    return recipe


def recipe_for(name: str, cat: str) -> dict:
    r: dict = {}
    n = name
    if cat == "DRINKS":
        for kw, ing in DRINKS:
            if kw.lower() in n.lower():
                add(r, ing)
                break
        if "(Hot)" not in n:  # cold drinks, juices and blended drinks need ice
            add(r, {"ICE": 300 if "lended" in n else 200})
        return r
    if cat == "FRUITS":
        return {FRUIT[n]: 250}
    if cat == "ADD ON":
        return {"White rice": {"RICE": 90}}.get(n, {"EGG": 1, "COOKING_OIL": 10})
    if cat == "SNACKS":
        for kw, ing in SNACKS.items():
            if kw in n:
                return add(add(r, ing), {"COOKING_OIL": 20, "SWEET_CHILI": 15})
    if cat == "BREAKFAST":
        if "Waffle" in n:
            add(r, {"WAFFLE_MIX": 80, "EGG": 0.5, "FRESH_MILK": 60})
            if "Premium" in n:
                add(r, {"CHOCOLATE_POWDER": 15, "OREO": 15})
        elif "Toast" in n:
            add(r, {"BREAD": 2, "CONDENSED_MILK": 15})
        elif "Egg Sandwich" in n:
            add(r, {"BREAD": 2, "EGG": 1})
        scoops = next((int(c) for c in n if c.isdigit()), 0)
        if "Ice" in n:
            add(r, {"ICE_CREAM": 60 * max(scoops, 1)})
        return r
    if cat in ("PASTA",) or (cat == "VEGETARIAN FOOD" and "Spaghetti" in n):
        add(r, {"SPAGHETTI": 120})
        for kw, ing in PASTA_SAUCE.items():
            if kw in n:
                add(r, {k: v for k, v in ing.items() if not (cat == "VEGETARIAN FOOD" and k in ("CHICKEN_BREAST", "SHRIMP"))})
        if cat == "VEGETARIAN FOOD":
            add(r, {"MIXED_VEG": 60})
        if "Chicken Chop" in n:
            add(r, {"CHICKEN_CHOP": 1})
        return r
    if "Noodle" in n:
        add(r, NOODLE_BASE)
        if cat != "VEGETARIAN FOOD":
            add(r, {"CHICKEN_BREAST": 40})
        else:
            add(r, {"MIXED_VEG": 40})
        if "Tomyam" in n:
            add(r, {"TOMYAM_PASTE": 25, "SHRIMP": 30})
        if "Pattaya" in n:
            add(r, {"EGG": 1, "TOMATO_SAUCE": 15})
        return r
    if "Ayam Gepuk" in n or "Ayam Penyet" in n:
        return add(r, {"CHICKEN_LEG": 250, "RICE": 90, "SAMBAL_PASTE": 30, "CHILI": 15, "MIXED_VEG": 30, "COOKING_OIL": 40})
    if "Nasi Tomato" in n:
        return add(r, {"RICE": 100, "TOMATO": 40, "CHICKEN_LEG": 250, "TOMATO_SAUCE": 30, "CHILI": 10, "COOKING_OIL": 20})
    if "Nasi Paprik" in n:
        return add(r, {**RICE_PLATE, "CHICKEN_BREAST": 120, "TOMATO_SAUCE": 25, "ONION": 20, "MIXED_VEG": 30, "COOKING_OIL": 20})
    if "Kangkung" in n:
        return {"KANGKUNG": 200, "SAMBAL_PASTE": 15, "GARLIC": 5, "COOKING_OIL": 15}
    if "Sayur Campur" in n:
        return {"MIXED_VEG": 200, "GARLIC": 5, "OYSTER_SAUCE": 10, "COOKING_OIL": 15}
    if "Seaweed" in n:
        return {"SEAWEED": 5, "EGG": 1, **RICE_PLATE}
    if "Porridge" in n:
        return {"RICE": 60, "ONION": 10, **({"TILAPIA": 100} if "Fish" in n else {"CHICKEN_BREAST": 80})}
    if "Mushroom Soup" in n:
        return {"MUSHROOM": 60, "COOKING_CREAM": 60, "BREAD": 1}
    if "Tomyam" in n and "Soup" in n:
        add(r, {"TOMYAM_PASTE": 30, "MIXED_VEG": 30, "LIME": 10})
        add(r, {"SHRIMP": 60, "TILAPIA": 60} if "Seafood" in n else {"CHICKEN_BREAST": 100})
        if cat != "ALA CARTE":
            add(r, RICE_PLATE)
        return r
    if "Nasi Goreng" in n or "Fried Rice" in n:
        add(r, FRIED_RICE)
        extras = {
            "Kampung": {"CHILI": 10, "KANGKUNG": 20}, "Tomyam": {"TOMYAM_PASTE": 20, "SHRIMP": 20, "CHICKEN_BREAST": 30},
            "Pattaya": {"EGG": 1, "CHICKEN_BREAST": 40, "TOMATO_SAUCE": 15}, "Cina": {"CHICKEN_BREAST": 30, "MIXED_VEG": 20},
            "Thai": {"SWEET_CHILI": 15, "CHICKEN_BREAST": 30}, "Teriyaki": {"TERIYAKI": 20, "CHICKEN_BREAST": 40},
            "Nenas": {"PINEAPPLE": 40, "SHRIMP": 20}, "Nasi Ayam": {"CHICKEN_LEG": 250},
        }
        for kw, ing in extras.items():
            if kw in n:
                add(r, ing)
        if cat == "VEGETARIAN FOOD":
            add(r, {"MIXED_VEG": 60})
        return r
    if "Fish & Chips" in n:
        return {"TILAPIA": 150, "SHOESTRING": 120, "MIXED_VEG": 40, "COOKING_OIL": 30}
    if "Chicken Chop" in n:
        add(r, {"CHICKEN_CHOP": 1, "COOKING_OIL": 25 if "Fried" in n else 5})
        add(r, RICE_PLATE if "Rice" in n else ({"SHOESTRING": 100, "MIXED_VEG": 50} if cat == "WESTERN FOOD" else {}))
        if "Egg" in n and "Salted" not in n:
            add(r, {"EGG": 1})
        for kw, ing in SAUCES:
            if kw in n:
                add(r, ing)
        return r
    # Chinese-style protein + sauce dishes (with rice unless a-la-carte)
    protein = {"SHRIMP": 80} if "Prawn" in n else {"TILAPIA": 130} if "Fish" in n else {"CHICKEN_BREAST": 120}
    add(r, protein)
    add(r, {"COOKING_OIL": 20})
    for kw, ing in SAUCES:
        if kw in n:
            add(r, ing)
            break
    if cat != "ALA CARTE":
        add(r, RICE_PLATE)
    return r


# --------------------------------------------------------------------------------------------
# Demand calendar (AIMST-area campus kopitiam)
# --------------------------------------------------------------------------------------------
def interp(d: date, points: list[tuple[str, float]]) -> float:
    xs = [D(p).toordinal() for p, _ in points]
    return float(np.interp(d.toordinal(), xs, [v for _, v in points]))


ACADEMIC = [  # (date, students-on-campus factor), linear between points
    ("2025-10-01", 0.70), ("2025-10-31", 0.76), ("2025-11-07", 1.00),
    ("2026-02-25", 1.00), ("2026-03-02", 0.45), ("2026-03-29", 0.45), ("2026-04-05", 1.00),
    ("2026-07-03", 1.00), ("2026-07-13", 1.15), ("2026-07-24", 1.18), ("2026-07-31", 1.05), ("2026-08-06", 0.42),
    ("2026-08-31", 0.42), ("2026-09-07", 0.48), ("2026-09-14", 0.66), ("2026-09-24", 0.58),
    ("2026-10-01", 0.52), ("2026-10-05", 0.56), ("2026-10-12", 0.74), ("2026-10-31", 0.76),
]
HOLIDAY_DIPS = {  # date -> factor (students go home)
    "2025-10-22": 0.85, "2025-10-23": 0.95,
    "2025-12-24": 0.80, "2025-12-25": 0.60, "2025-12-26": 0.75,
    "2025-12-31": 0.80, "2026-01-01": 0.60, "2026-01-02": 0.80,
    "2026-02-13": 0.85, "2026-02-14": 0.70, "2026-02-15": 0.55, "2026-02-16": 0.45, "2026-02-17": 0.35,
    "2026-02-18": 0.40, "2026-02-19": 0.55, "2026-02-20": 0.70, "2026-02-21": 0.80, "2026-02-22": 0.90,
    "2026-03-18": 0.75, "2026-03-19": 0.60, "2026-03-20": 0.45, "2026-03-21": 0.45, "2026-03-22": 0.60,
    "2026-03-23": 0.75,
    "2026-05-01": 0.75, "2026-05-02": 0.85,
    "2026-05-27": 0.75, "2026-05-28": 0.80, "2026-05-30": 0.85, "2026-05-31": 0.80, "2026-06-01": 0.75,
    "2026-06-17": 0.85, "2026-08-26": 0.85, "2026-08-31": 0.80, "2026-09-16": 0.80,
}
CELEBRATION_NIGHTS = {  # student-organised festive events after the holiday
    "2025-11-06": 1.08, "2025-11-07": 1.35,   # Deepavali night
    "2026-01-09": 1.30,                        # Christmas & New Year party
    "2026-02-27": 1.35,                        # CNY celebration
    "2026-04-09": 1.08, "2026-04-10": 1.40,   # Raya open house
}
EVENT_CAT_BOOST = {"DRINKS": 1.15, "SNACKS": 1.30}
EXPIRED_DEMO = {"FRESH_MILK": 9, "BREAD": 6, "MANGO": 7}   # days since last purchase > shelf life
EXPIRING_DEMO = {"EGG": 12}                                 # expires within 2 days of the count

# What the owner would know in advance (academic calendar, public holidays, announced student events).
# The app learns each type's effect from history; sales data itself carries no reasons.
CALENDAR = [  # type (period/public_holiday/local_event), label (what the model learns per), start, end, name
    ("period", "break", "2025-08-01", "2025-11-01", "Semester break"),
    ("period", "intake", "2025-10-06", "2025-10-31", "October intake"),
    ("period", "semester", "2025-11-02", "2026-02-28", "Semester"),
    ("period", "break", "2026-03-01", "2026-04-04", "March break"),
    ("period", "semester", "2026-04-05", "2026-07-31", "Semester"),
    ("period", "intake", "2026-07-06", "2026-07-31", "July intake"),
    ("period", "break", "2026-08-01", "2026-11-01", "Semester break"),
    ("period", "intake", "2026-09-07", "2026-09-25", "September intake"),
    ("period", "intake", "2026-10-05", "2026-10-31", "October intake"),
    ("period", "semester", "2026-11-02", "2027-02-27", "Semester"),
    ("public_holiday", "public_holiday", "2025-10-20", "2025-10-20", "Deepavali"),
    ("public_holiday", "public_holiday", "2025-12-25", "2025-12-25", "Christmas"),
    ("public_holiday", "public_holiday", "2026-01-01", "2026-01-01", "New Year"),
    ("public_holiday", "public_holiday", "2026-02-17", "2026-02-18", "Chinese New Year"),
    ("public_holiday", "public_holiday", "2026-03-20", "2026-03-21", "Hari Raya Aidilfitri"),
    ("public_holiday", "public_holiday", "2026-05-01", "2026-05-01", "Labour Day"),
    ("public_holiday", "public_holiday", "2026-05-27", "2026-05-28", "Hari Raya Haji"),
    ("public_holiday", "public_holiday", "2026-05-31", "2026-06-01", "Wesak / Agong's Birthday"),
    ("public_holiday", "public_holiday", "2026-06-17", "2026-06-17", "Awal Muharram"),
    ("public_holiday", "public_holiday", "2026-08-26", "2026-08-26", "Maulidur Rasul"),
    ("public_holiday", "public_holiday", "2026-08-31", "2026-08-31", "Merdeka Day"),
    ("public_holiday", "public_holiday", "2026-09-16", "2026-09-16", "Malaysia Day"),
    ("public_holiday", "public_holiday", "2026-11-08", "2026-11-08", "Deepavali"),
    ("public_holiday", "public_holiday", "2026-12-25", "2026-12-25", "Christmas"),
    ("local_event", "local_event", "2025-11-07", "2025-11-07", "Deepavali night"),
    ("local_event", "local_event", "2026-01-09", "2026-01-09", "Year-end party"),
    ("local_event", "local_event", "2026-02-27", "2026-02-27", "CNY celebration"),
    ("local_event", "local_event", "2026-04-10", "2026-04-10", "Raya open house"),
    ("local_event", "local_event", "2026-11-20", "2026-11-20", "Deepavali night"),
]
SOFT_PERIODS = [("2025-12-20", "2026-01-03", 0.92), ("2026-02-19", "2026-03-19", 0.92)]
DOW = {"default": [1.06, 1.08, 1.08, 1.05, 0.95, 0.85, 0.78],
       "BREAKFAST": [1.18, 1.18, 1.18, 1.15, 1.02, 0.72, 0.60]}


def day_factor(d: date) -> float:
    f = interp(d, ACADEMIC) * HOLIDAY_DIPS.get(d.isoformat(), 1.0) * CELEBRATION_NIGHTS.get(d.isoformat(), 1.0)
    for a, b, v in SOFT_PERIODS:
        if D(a) <= d <= D(b):
            f *= v
    return f * (1 + 0.04 * (d - START).days / DAYS)  # mild business growth


# --------------------------------------------------------------------------------------------
def main() -> None:
    menu = list(csv.DictReader(open(HERE / "menu_profile.csv", encoding="utf-8")))
    recipes = {}
    for m in menu:
        r = recipe_for(m["name"], m["category"])
        assert r and set(r) <= ING_IDS, f"bad recipe for {m['name']}: {r}"
        recipes[m["item_id"]] = r

    dates = [START + timedelta(days=i) for i in range(DAYS)]
    day_noise = rng.lognormal(0, 0.07, DAYS)
    sales_rows, totals, usage = [], [], np.zeros((DAYS, len(INGREDIENTS)))
    ing_index = {ing[0]: i for i, ing in enumerate(INGREDIENTS)}
    for di, d in enumerate(dates):
        base = BASE_ITEMS_PER_DAY * day_factor(d) * day_noise[di]
        celebration = d.isoformat() in CELEBRATION_NIGHTS and CELEBRATION_NIGHTS[d.isoformat()] > 1.2
        day_total = 0
        for m in menu:
            if m["launch_date"] and d < D(m["launch_date"]):
                continue
            cat = m["category"]
            mu = base * float(m["share"]) * DOW.get(cat, DOW["default"])[d.weekday()]
            if celebration:
                mu *= EVENT_CAT_BOOST.get(cat, 1.0)
            qty = int(rng.negative_binomial(DISPERSION, DISPERSION / (DISPERSION + mu))) if mu > 0 else 0
            if qty:
                price = float(m["price_rm"])
                sales_rows.append([d.isoformat(), m["item_id"], m["name"], cat, qty, f"{price:.2f}", f"{qty * price:.2f}"])
                day_total += qty
                for ing, q in recipes[m["item_id"]].items():
                    usage[di, ing_index[ing]] += q * qty
        totals.append(day_total)

    write("daily_sales.csv", ["date", "item_id", "item_name", "category", "qty", "unit_price_rm", "net_sales_rm"], sales_rows)
    write("menu_items.csv", ["item_id", "name", "category", "price_rm", "launch_date"],
          [[m["item_id"], m["name"], m["category"], m["price_rm"], m["launch_date"]] for m in menu])
    write("suppliers.csv", ["supplier_id", "name", "category", "delivery_days", "lead_time_days", "min_order_rm", "whatsapp"], SUPPLIERS)
    write("ingredients.csv", ["ingredient_id", "name", "supplier_id", "storage", "base_uom", "pack_uom",
                              "pack_size_base", "pack_price_rm", "shelf_life_days", "waste_pct"], INGREDIENTS)
    write("recipes.csv", ["item_id", "item_name", "ingredient_id", "qty_per_serving", "base_uom"],
          [[m["item_id"], m["name"], ing, round(q, 2), INGREDIENTS[ing_index[ing]][4]]
           for m in menu for ing, q in recipes[m["item_id"]].items()])

    # Opening inventory counted on the morning after the last sales day, with last purchase dates.
    # Long-life items are stocked deep (rice, sauces); perishables are thin and bought often.
    count_date = dates[-1] + timedelta(days=1)
    recent = usage[-14:].mean(axis=0)
    stock = []
    for i, ing in enumerate(INGREDIENTS):
        ing_id, life = ing[0], ing[8]
        if ing_id in EXPIRED_DEMO:
            days_ago, cover = EXPIRED_DEMO[ing_id], rng.uniform(0.3, 0.6)
        elif ing_id in EXPIRING_DEMO:
            days_ago, cover = EXPIRING_DEMO[ing_id], rng.uniform(0.8, 1.5)
        elif ing[2] == "SUP-FRZ":
            days_ago, cover = int(rng.choice([3, 7])), rng.uniform(1.5, 5) if life < 180 else rng.uniform(6, 20)
        elif life >= 180:
            days_ago, cover = int(rng.integers(3, 31)), rng.uniform(6, 20)
        elif life >= 30:
            days_ago, cover = int(rng.integers(2, 11)), rng.uniform(1.5, 5)
        elif life >= 7:
            days_ago, cover = int(rng.integers(1, 5)), rng.uniform(0.5, 2)
        else:
            days_ago, cover = int(rng.integers(0, life)), rng.uniform(0.2, 0.8)
        qty = recent[i] * cover
        qty = round(qty) if ing[4] == "pcs" else int(round(qty, -1))
        stock.append([ing_id, ing[1], max(qty, 1), ing[4], (count_date - timedelta(days=days_ago)).isoformat(),
                      count_date.isoformat()])
    write("inventory.csv", ["ingredient_id", "name", "qty_base", "base_uom", "last_purchased_date", "counted_on"], stock)
    write("calendar_events.csv", ["type", "label", "start_date", "end_date", "name"], CALENDAR)

    plot(dates, totals)
    print(f"{len(sales_rows)} sales rows, {len(menu)} items, {len(INGREDIENTS)} ingredients, "
          f"mean {np.mean(totals):.0f} items/day, revenue RM{sum(float(r[6]) for r in sales_rows):,.0f}")


def write(name: str, header: list, rows) -> None:
    with open(HERE / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def plot(dates, totals) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(14, 4.5))
    ax.plot(dates, totals, lw=0.8, color="#1f6feb")
    week = np.convolve(totals, np.ones(7) / 7, mode="valid")
    ax.plot(dates[3:-3], week, lw=2, color="#d1242f", label="7-day average")
    ax.set_title("Synthetic daily items sold (campus kopitiam)")
    ax.set_ylabel("items / day")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(HERE / "daily_totals.png", dpi=110)


if __name__ == "__main__":
    main()
