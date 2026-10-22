"""Requirements and shelf-life-aware purchasing, on small hand-made cases and on the demo data."""
import time
from datetime import date, timedelta

import pandas as pd
import pytest

from app.config import REPO_ROOT
from app.engine.forecast import forecast
from app.engine.purchasing import plan_purchases
from app.engine.requirements import requirements
from app.engine.safety import safety_profiles

TODAY = date(2026, 10, 22)


def d(n: int) -> date:
    """Day n of the plan: 0 = today, 1 = tomorrow ..."""
    return TODAY + timedelta(days=n)


def plan(needs, *, stock=0.0, bought=None, shelf=30, pack=1000.0, price=10.0, buffer=0.2, min_order=0.0,
         safety=True, ingredient="X"):
    """One ingredient. needs[i] = forecast use on day i (day 0 = today)."""
    need_df = pd.DataFrame({"date": [d(i) for i in range(len(needs))], "ingredient_id": ingredient,
                            "need_base": needs})
    inv = pd.DataFrame({"ingredient_id": [ingredient], "qty_base": [stock],
                        "last_purchased_on": [bought if bought else d(-1)]})
    ing = pd.DataFrame({"ingredient_id": [ingredient], "name": ["Test item"], "supplier_id": [1],
                        "base_uom": ["g"], "pack_uom": ["PKT (1kg)"], "pack_size_base": [pack],
                        "pack_price_rm": [price], "shelf_life_days": [shelf]})
    sup = pd.DataFrame({"supplier_id": [1], "name": ["Supplier A"], "min_order_rm": [min_order]})
    rows = [(ingredient, h, 0.9, buffer, 40, "measured") for h in range(1, 8)] if safety else []
    saf = pd.DataFrame(rows, columns=["ingredient_id", "horizon", "service_level", "buffer", "n_samples", "method"])
    return plan_purchases(need_df, inv, ing, sup, saf, TODAY, len(needs) - 1)


def only_line(result):
    lines = [l for s in result["suppliers"] for l in s["lines"]]
    assert len(lines) == 1
    return lines[0]


# ---------- requirements ----------
def test_requirements_multiply_dishes_by_recipes_and_flag_missing_recipes():
    dishes = pd.DataFrame({"date": [d(1), d(1), d(2), d(2), d(2)], "item_id": ["A", "B", "A", "B", "C"],
                           "qty": [10.0, 5.0, 20.0, 0.0, 7.0]})
    recipes = pd.DataFrame({"item_id": ["A", "A", "B"], "ingredient_id": ["rice", "egg", "rice"],
                            "qty_per_serving": [150.0, 1.0, 100.0]})
    r = requirements(dishes, recipes, {"C": "Mystery dish"})
    need = r.need.set_index(["date", "ingredient_id"]).need_base
    assert need[(d(1), "rice")] == 10 * 150 + 5 * 100 and need[(d(1), "egg")] == 10
    assert need[(d(2), "rice")] == 20 * 150
    assert r.exceptions == [{"type": "dish_without_recipe", "item_id": "C", "name": "Mystery dish", "expected_qty": 7.0}]
    assert r.multiplications == 6  # A has 2 recipe lines (x2 days), B has 1 (x2 days); C has none


# ---------- expiry ----------
def test_expired_stock_is_excluded_and_listed_for_discarding():
    # 500 g bought 10 days ago with a 3-day shelf life: expired, must not count as stock
    res = plan([0, 100, 100], stock=500, bought=d(-10), shelf=3, pack=1000)
    assert res["discard"] == [
        {"ingredient_id": "X", "name": "Test item", "qty_base": 500.0, "expired_on": d(-7).isoformat(), "days_ago": 7}
    ]
    line = only_line(res)
    assert line["usable_stock_base"] == 0 and line["suggested_packs"] == 1
    assert line["explanation"]["stock"]["expired"] is True


def test_stock_that_expires_today_is_not_usable():
    res = plan([0, 100], stock=500, bought=d(-3), shelf=3)  # bought -3 + 3 days = today -> expired
    assert len(res["discard"]) == 1 and only_line(res)["usable_stock_base"] == 0


def test_stock_that_expires_mid_horizon_only_counts_until_then():
    # 300 g good until day 3 (bought day -1, shelf 4 -> expires day 3). Need 100/day: covers days 1-2 only.
    res = plan([0, 100, 100, 100, 100], stock=300, bought=d(-1), shelf=4, pack=500, buffer=0.0)
    line = only_line(res)
    assert [t["date"] for t in line["explanation"]["trips"]] == [d(3).isoformat()]


# ---------- trips for short shelf life ----------
def test_short_shelf_life_gives_several_dated_buys():
    res = plan([0] + [100] * 6, shelf=2, pack=1000, buffer=0.2)
    line = only_line(res)
    assert [t["date"] for t in line["buy_schedule"]] == [d(1).isoformat(), d(3).isoformat(), d(5).isoformat()]
    first = line["explanation"]["trips"][0]
    assert (first["window_start"], first["window_end"], first["window_days"]) == (d(1).isoformat(), d(2).isoformat(), 2)
    assert first["target_base"] == pytest.approx(240) and line["suggested_packs"] == 3
    assert line["line_total_rm"] == 30.0
    # every pack but the last is thrown away after 2 days; the last one (bought day 5, 200 g used) is still fresh
    assert line["explanation"]["leftover_base"] == pytest.approx(800)


def test_one_day_shelf_life_buys_every_day():
    line = only_line(plan([0] + [100] * 3, shelf=1, pack=500, buffer=0.0))
    assert [t["date"] for t in line["buy_schedule"]] == [d(1).isoformat(), d(2).isoformat(), d(3).isoformat()]


def test_long_life_item_buys_once_for_the_whole_horizon_with_a_buffer():
    line = only_line(plan([0] + [100] * 5, shelf=365, pack=500, buffer=0.3))
    assert len(line["buy_schedule"]) == 1 and line["buy_schedule"][0]["date"] == d(1).isoformat()
    t = line["explanation"]["trips"][0]
    assert t["window_days"] == 5 and t["window_need_base"] == 500 and t["target_base"] == pytest.approx(650)
    assert line["suggested_packs"] == 2  # ceil(650 / 500)
    assert line["buffer_pct"] == 30.0 and line["buffer_base"] == pytest.approx(150)
    assert line["need_base"] == 500  # tomorrow onwards; today's use is reported separately


def test_long_life_item_with_enough_stock_is_not_bought():
    res = plan([100] * 4, stock=10_000, shelf=365)
    assert res["suppliers"] == [] and res["grand_total_rm"] == 0
    assert [c["ingredient_id"] for c in res["covered"]] == ["X"]


# ---------- stock, today's use, leftovers ----------
def test_todays_use_is_taken_from_stock_before_tomorrow():
    # 500 g in stock, 300 g used today -> only 200 g usable for tomorrow (need 300)
    line = only_line(plan([300, 300, 300], stock=500, shelf=30, pack=100, buffer=0.0))
    assert line["today_use_base"] == 300 and line["usable_stock_base"] == 200
    assert line["suggested_packs"] == 4  # 600 needed - 200 usable = 400


def test_leftovers_are_carried_forward_so_later_trips_buy_less():
    with_stock = only_line(plan([0] + [100] * 5, stock=250, shelf=30, pack=100, buffer=0.2))
    t = with_stock["explanation"]["trips"]
    assert len(t) == 1 and t[0]["date"] == d(3).isoformat()  # stock covers days 1-2, the trip is on day 3
    assert t[0]["usable_base"] == pytest.approx(50)
    assert with_stock["suggested_packs"] == 4  # target 360 - 50 usable = 310 -> 4 packs
    no_stock = only_line(plan([0] + [100] * 5, stock=0, shelf=30, pack=100, buffer=0.2))
    assert no_stock["suggested_packs"] == 6  # target 600


def test_pack_rounding_leftover_is_reported():
    line = only_line(plan([0, 100, 100, 100], shelf=30, pack=1000, buffer=0.2))
    assert line["leftover_base"] == pytest.approx(700)  # 1000 bought, 300 used


def test_zero_stock_today_short_is_raised_as_an_exception():
    res = plan([100, 100], stock=0, shelf=30)
    assert any(e["type"] == "short_today" for e in res["exceptions"])


# ---------- buffer lookup ----------
def test_missing_safety_row_falls_back_to_15_percent_and_says_so():
    line = only_line(plan([0, 100, 100], shelf=30, pack=100, safety=False))
    assert line["buffer_pct"] == 15.0 and line["explanation"]["method"] == "default"
    assert line["suggested_packs"] == 3  # 230 -> 3 packs


def test_buffer_is_looked_up_by_window_length():
    # two trips of different window lengths use their own buffers
    need_df = pd.DataFrame({"date": [d(i) for i in range(5)], "ingredient_id": "X", "need_base": [0, 100, 100, 100, 100]})
    inv = pd.DataFrame({"ingredient_id": ["X"], "qty_base": [0.0], "last_purchased_on": [d(-1)]})
    ing = pd.DataFrame({"ingredient_id": ["X"], "name": ["T"], "supplier_id": [1], "base_uom": ["g"], "pack_uom": ["P"],
                        "pack_size_base": [10.0], "pack_price_rm": [1.0], "shelf_life_days": [3]})
    sup = pd.DataFrame({"supplier_id": [1], "name": ["S"], "min_order_rm": [0.0]})
    saf = pd.DataFrame([("X", h, 0.8, b, 30, "measured") for h, b in [(1, 0.5), (2, 0.4), (3, 0.3), (4, 0.2)]],
                       columns=["ingredient_id", "horizon", "service_level", "buffer", "n_samples", "method"])
    res = plan_purchases(need_df, inv, ing, sup, saf, TODAY, 4)
    trips = only_line(res)["explanation"]["trips"]
    assert [(t["window_days"], t["buffer_pct"]) for t in trips] == [(3, 30.0), (1, 50.0)]


# ---------- suppliers, totals, warnings ----------
def test_supplier_subtotal_grand_total_and_minimum_order_warning():
    res = plan([0, 100], shelf=30, pack=1000, price=12.5, min_order=50)
    sup = res["suppliers"][0]
    assert sup["subtotal_rm"] == 12.5 and res["grand_total_rm"] == 12.5
    assert sup["warnings"] == ["Below the supplier's minimum order of RM 50.00"]
    assert plan([0, 100], pack=1000, price=60, min_order=50)["suppliers"][0]["warnings"] == []


def test_ingredient_no_recipe_uses_is_flagged():
    need_df = pd.DataFrame({"date": [d(1)], "ingredient_id": ["X"], "need_base": [10.0]})
    inv = pd.DataFrame({"ingredient_id": ["X", "Y"], "qty_base": [0.0, 5.0], "last_purchased_on": [d(-1)] * 2})
    ing = pd.DataFrame({"ingredient_id": ["X", "Y"], "name": ["X", "Unused spice"], "supplier_id": [1, 1],
                        "base_uom": ["g"] * 2, "pack_uom": ["P"] * 2, "pack_size_base": [10.0] * 2,
                        "pack_price_rm": [1.0] * 2, "shelf_life_days": [30] * 2})
    sup = pd.DataFrame({"supplier_id": [1], "name": ["S"], "min_order_rm": [0.0]})
    saf = pd.DataFrame(columns=["ingredient_id", "horizon", "service_level", "buffer", "n_samples", "method"])
    res = plan_purchases(need_df, inv, ing, sup, saf, TODAY, 1, exceptions=[{"type": "dish_without_recipe"}])
    kinds = [e["type"] for e in res["exceptions"]]
    assert kinds == ["dish_without_recipe", "no_forecast_use"]
    assert [e["name"] for e in res["exceptions"] if e["type"] == "no_forecast_use"] == ["Unused spice"]


def test_explanation_carries_everything_the_why_sentence_needs():
    ex = only_line(plan([600, 100, 100, 100], stock=700, bought=d(-5), shelf=60, pack=1000, buffer=0.25))["explanation"]
    assert {"daily_need", "stock", "trips", "service_level", "n_samples", "method", "leftover_base"} <= ex.keys()
    assert ex["stock"] == {"qty_base": 700.0, "expires_on": d(55).isoformat(), "expired": False,
                           "purchase_date_unknown": False}
    assert ex["service_level"] == 0.9 and ex["n_samples"] == 40 and len(ex["daily_need"]) == 4


# ---------- the full pipeline on the demo data ----------
DATA = REPO_ROOT / "data"


@pytest.fixture(scope="module")
def demo():
    sales = pd.read_csv(DATA / "daily_sales.csv", parse_dates=["date"])[["date", "item_id", "qty"]]
    menu = pd.read_csv(DATA / "menu_items.csv")[["item_id", "category", "launch_date"]]
    cal = pd.read_csv(DATA / "calendar_events.csv", parse_dates=["start_date", "end_date"])
    rec = pd.read_csv(DATA / "recipes.csv")[["item_id", "ingredient_id", "qty_per_serving"]]
    ing = pd.read_csv(DATA / "ingredients.csv")
    sup = pd.read_csv(DATA / "suppliers.csv")
    inv = pd.read_csv(DATA / "inventory.csv", parse_dates=["last_purchased_date"]).rename(
        columns={"last_purchased_date": "last_purchased_on"})
    return dict(sales=sales, menu=menu, cal=cal, rec=rec, ing=ing, sup=sup, inv=inv)


def run_demo(demo, horizon, safety=None):
    t = demo
    fc = forecast(t["sales"], t["menu"], t["cal"], TODAY, horizon + 1)  # today + the horizon
    reqs = requirements(fc, t["rec"])
    safety = safety if safety is not None else safety_profiles(
        pd.DataFrame(columns=["ingredient_id", "horizon", "origin", "rel_err"]), t["ing"]).rename(columns={})
    return plan_purchases(reqs.need, t["inv"][["ingredient_id", "qty_base", "last_purchased_on"]],
                          t["ing"][["ingredient_id", "name", "supplier_id", "base_uom", "pack_uom", "pack_size_base",
                                    "pack_price_rm", "shelf_life_days"]],
                          t["sup"][["supplier_id", "name", "min_order_rm"]], safety, TODAY, horizon,
                          reqs.exceptions)


def test_seven_day_plan_on_demo_data_takes_under_a_second(demo):
    run_demo(demo, 7)  # warm-up (imports, caches)
    started = time.perf_counter()
    res = run_demo(demo, 7)
    elapsed = time.perf_counter() - started
    assert elapsed < 1.0, f"7-day plan took {elapsed:.2f}s"
    assert res["calc_count"] > 1000 and res["grand_total_rm"] > 0


def test_demo_plan_discards_expired_items_and_buys_fresh_ones_in_trips(demo):
    res = run_demo(demo, 7)
    discarded = {x["ingredient_id"] for x in res["discard"]}
    assert {"FRESH_MILK", "MANGO"} <= discarded and len(discarded) == 3
    lines = {l["ingredient_id"]: l for s in res["suppliers"] for l in s["lines"]}
    assert len(lines["ICE"]["buy_schedule"]) >= 4  # 1-day shelf life: bought most days
    assert all(t["buffer_pct"] == 15.0 for t in lines["ICE"]["explanation"]["trips"])  # no history-based buffers given
    assert "RICE" not in lines or lines["RICE"]["suggested_packs"] >= 0
    assert res["exceptions"] == [] or all(e["type"] != "dish_without_recipe" for e in res["exceptions"])
    totals = sum(s["subtotal_rm"] for s in res["suppliers"])
    assert res["grand_total_rm"] == pytest.approx(totals)
