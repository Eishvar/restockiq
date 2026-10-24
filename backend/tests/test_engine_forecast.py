"""Forecast, backtest and safety-buffer tests, including comparison with data/reference_forecast.py."""
import importlib.util
import sys
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from app.config import REPO_ROOT
from app.engine.backtest import backtest_all, rolling_origins
from app.engine.calendar import calendar_features
from app.engine.forecast import (
    flat_avg_4w,
    forecast,
    forecast_detail,
    forecast_wide,
    menu_frame,
    naive_last_week,
    sales_to_wide,
)
from app.engine.safety import safety_profiles, service_level

DATA = REPO_ROOT / "data"


# ---------- the reference prototype ----------
@pytest.fixture(scope="module")
def ref():
    spec = importlib.util.spec_from_file_location("reference_forecast", DATA / "reference_forecast.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["reference_forecast"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def world(ref):
    """The reference's own loader output plus the engine-shaped (long) versions of the same data."""
    q, menu, cal, bom, ing = ref.load(str(DATA))
    calf = ref.calendar_features(cal, pd.date_range(q.index.min(), q.index.max() + timedelta(days=14)))
    sales = pd.read_csv(DATA / "daily_sales.csv", parse_dates=["date"])[["date", "item_id", "qty"]]
    menu_df = menu.reset_index()[["item_id", "category", "launch_date"]]
    return dict(q=q, menu=menu, cal=cal, bom=bom, ing=ing, calf=calf, sales=sales, menu_df=menu_df)


REF_ORIGINS = pd.date_range("2026-03-03", "2026-10-15", freq="5D")


@pytest.fixture(scope="module")
def ref_backtest(world):
    """Engine backtest run on the reference's own origins (same protocol as reference_forecast.py)."""
    w = world
    return backtest_all(w["q"], w["menu"], w["calf"], w["bom"], REF_ORIGINS, horizons=(1, 3, 7))


@pytest.fixture(scope="module")
def weekly_backtest(world):
    """Engine backtest with the app's protocol: an origin every 3 days over the last 34 weeks, horizons 1-7."""
    w = world
    origins = rolling_origins(w["q"].index.min(), w["q"].index.max())
    return backtest_all(w["q"], w["menu"], w["calf"], w["bom"], origins)


# ---------- port matches the reference exactly ----------
def test_calendar_features_match_reference(ref, world):
    dates = pd.date_range("2025-10-22", "2026-11-04")
    mine = calendar_features(world["cal"], dates)
    theirs = ref.calendar_features(world["cal"], dates)
    assert (mine.state.values == theirs.state.values).all()
    assert (mine.holiday.values == theirs.holiday.values).all()
    assert (mine.event.values == theirs.event.values).all()


@pytest.mark.parametrize("origin", ["2026-03-03", "2026-07-20", "2026-10-15", "2026-10-22"])
def test_forecast_matches_reference_values(ref, world, origin):
    w = world
    mine, _ = forecast_wide(w["q"], w["menu"], w["calf"], origin, 7)
    theirs = ref.forecast(w["q"], w["menu"], w["calf"], pd.Timestamp(origin), 7)
    np.testing.assert_allclose(mine.to_numpy(), theirs.to_numpy(), rtol=1e-9, atol=1e-9)


def test_public_forecast_from_long_data_matches_reference(ref, world):
    w = world
    lines = forecast(w["sales"], w["menu_df"], w["cal"], "2026-10-22", 7)
    assert list(lines.columns) == ["date", "item_id", "qty", "drivers"]
    theirs = ref.forecast(w["q"], w["menu"], w["calf"], pd.Timestamp("2026-10-22"), 7)
    mine = lines.pivot(index="date", columns="item_id", values="qty")
    np.testing.assert_allclose(mine.to_numpy(), theirs.reindex(columns=mine.columns).to_numpy(), rtol=1e-9)


def test_forecast_drivers_explain_each_day(world):
    w = world
    fc = forecast_detail(w["sales"], w["menu_df"], w["cal"], "2026-10-22", 7)
    assert len(fc.days) == 7
    d = fc.days.iloc[0]["drivers"]
    assert d["weekday"] == "Thu" and d["state"] and d["cold_start"] is False
    assert {"weekday_factor", "level", "strength", "holiday_effect", "event_effect", "names"} <= d.keys()
    # day totals equal the sum of the dishes
    by_day = fc.lines.groupby("date").qty.sum()
    np.testing.assert_allclose(by_day.values, fc.days.total.values, rtol=1e-9)


# ---------- accuracy ----------
def test_daily_total_wape_matches_reference_and_beats_baselines(weekly_backtest, ref_backtest):
    row = ref_backtest.quality.set_index("horizon_days").loc[7]
    assert abs(row.wape_total - 0.131) < 0.01  # reference prints 13.1%
    assert row.wape_total < row.baseline_naive_wape  # reference-like numbers: ~19-23%
    assert row.wape_total < row.baseline_flat_wape  # ~26-28%
    assert 0.17 < row.baseline_naive_wape < 0.25 and 0.24 < row.baseline_flat_wape < 0.30
    assert 0.55 < row.wape_items < 0.70  # single dishes are noisy (reference 62.6%)
    # the app's own protocol agrees: model beats both baselines at every horizon
    for r in weekly_backtest.quality.itertuples():
        assert r.wape_total < r.baseline_naive_wape and r.wape_total < r.baseline_flat_wape


# ---------- buffers vs the reference ----------
PICK = ["CHICKEN_BREAST", "RICE", "EGG"]
REF_BUFFER_H3 = {"CHICKEN_BREAST": 0.29, "RICE": 0.32, "EGG": 0.29}  # printed by reference_forecast.py


def _buffers(result, ing, risk="balanced"):
    ingredients = ing.reset_index()[["ingredient_id", "shelf_life_days"]]
    return safety_profiles(result.errors, ingredients, risk).set_index(["ingredient_id", "horizon"])


def test_buffers_equal_reference_on_reference_protocol(ref, world, ref_backtest):
    w = world
    errs = ref.backtest(w["q"], w["menu"], w["calf"], w["bom"], REF_ORIGINS)
    theirs = ref.safety_buffers(errs, w["ing"], ref.default_service_level).set_index(["ingredient_id", "horizon"])
    mine = _buffers(ref_backtest, w["ing"])
    for g in PICK:
        assert mine.loc[(g, 3), "buffer"] == pytest.approx(theirs.loc[(g, 3), "buffer"], abs=1e-9)
        assert mine.loc[(g, 3), "service_level"] == theirs.loc[(g, 3), "service_level"]


def test_buffers_within_five_points_on_app_protocol(world, weekly_backtest):
    mine = _buffers(weekly_backtest, world["ing"])
    for g, expected in REF_BUFFER_H3.items():
        got = mine.loc[(g, 3), "buffer"]
        assert abs(got - expected) <= 0.05, f"{g}: {got:.3f} vs reference {expected}"
        assert mine.loc[(g, 3), "method"] == "measured" and mine.loc[(g, 3), "n_samples"] >= 12


def test_shorter_horizons_need_bigger_buffers(world, weekly_backtest):
    mine = _buffers(weekly_backtest, world["ing"])
    assert mine.loc[("CHICKEN_BREAST", 1), "buffer"] > mine.loc[("CHICKEN_BREAST", 7), "buffer"]


def test_risk_profile_changes_buffers(world, weekly_backtest):
    lean = _buffers(weekly_backtest, world["ing"], "lean").loc[("RICE", 3), "buffer"]
    bal = _buffers(weekly_backtest, world["ing"], "balanced").loc[("RICE", 3), "buffer"]
    never = _buffers(weekly_backtest, world["ing"], "never_run_out").loc[("RICE", 3), "buffer"]
    assert lean < bal < never


# ---------- safety maths in isolation ----------
def test_service_level_table():
    assert [service_level(d, "balanced") for d in (3, 10, 60)] == [0.80, 0.90, 0.95]
    assert [service_level(d, "lean") for d in (3, 10, 60)] == [0.70, 0.80, 0.90]
    assert [service_level(d, "never_run_out") for d in (3, 10, 60)] == [0.90, 0.95, 0.98]
    assert service_level(6, "balanced") == 0.80 and service_level(7, "balanced") == 0.90
    assert service_level(29, "balanced") == 0.90 and service_level(30, "balanced") == 0.95


def _errors(values, ingredient="X", horizon=3):
    return pd.DataFrame({"ingredient_id": ingredient, "horizon": horizon, "origin": 0, "rel_err": values})


ING = pd.DataFrame({"ingredient_id": ["X", "NEW"], "shelf_life_days": [60, 60]})


def test_buffer_is_the_quantile_clipped_and_flagged_measured():
    p = safety_profiles(_errors(np.linspace(0, 0.4, 101)), ING, "balanced").set_index(["ingredient_id", "horizon"])
    row = p.loc[("X", 3)]
    assert row.buffer == pytest.approx(0.38) and row.method == "measured" and row.n_samples == 101
    p = safety_profiles(_errors(np.linspace(0, 2.0, 101)), ING).set_index(["ingredient_id", "horizon"])
    assert p.loc[("X", 3), "buffer"] == 0.60  # clipped at 60%
    p = safety_profiles(_errors(np.linspace(-0.9, -0.5, 101)), ING).set_index(["ingredient_id", "horizon"])
    assert p.loc[("X", 3), "buffer"] == 0.0  # forecast was too high: no buffer needed


def test_fewer_than_12_samples_use_the_15_percent_default():
    p = safety_profiles(_errors([0.5] * 11), ING).set_index(["ingredient_id", "horizon"])
    assert p.loc[("X", 3), "buffer"] == 0.15 and p.loc[("X", 3), "method"] == "default"
    assert p.loc[("X", 3), "n_samples"] == 11
    p = safety_profiles(_errors([0.5] * 12), ING).set_index(["ingredient_id", "horizon"])
    assert p.loc[("X", 3), "method"] == "measured"
    # an ingredient with no errors at all still gets a (default) value for every horizon
    assert (p.loc["NEW"].buffer == 0.15).all() and len(p.loc["NEW"]) == 7


def test_rolling_origins():
    o = rolling_origins("2025-10-22", "2026-10-21")
    assert len(o) == 80 and o[-1] == pd.Timestamp("2026-10-15") and (np.diff(o) == pd.Timedelta(days=3)).all()
    assert rolling_origins("2026-09-01", "2026-10-21") == []  # < 8 weeks of history before any origin


# ---------- behaviour on small synthetic restaurants ----------
def synth(n_days, total, share=None, start="2025-01-01"):
    """Sales for dishes A (and B) whose daily total follows total(day_index, date)."""
    share = share or {"A": 1.0}
    dates = pd.date_range(start, periods=n_days)
    rows = [(d, item, total(i, d) * s) for i, d in enumerate(dates) for item, s in share.items()]
    return pd.DataFrame(rows, columns=["date", "item_id", "qty"]), dates


def menu_of(items=("A",), launch=None):
    return pd.DataFrame(
        {"item_id": list(items), "category": "main", "launch_date": [(launch or {}).get(i) for i in items]}
    )


NO_CAL = pd.DataFrame(columns=["type", "label", "start_date", "end_date", "name"])


def totals(fc):
    return fc.days.set_index("date").total


def test_learns_the_weekday_pattern():
    factor = {5: 2.0, 6: 0.5}  # Saturday busy, Sunday quiet
    sales, dates = synth(140, lambda i, d: 100 * factor.get(d.dayofweek, 1.0))
    t = totals(forecast_detail(sales, menu_of(), NO_CAL, dates[-1] + timedelta(days=1), 7))
    by_wd = {d.dayofweek: v for d, v in t.items()}
    assert by_wd[5] / by_wd[0] == pytest.approx(2.0, rel=0.03)
    assert by_wd[6] / by_wd[0] == pytest.approx(0.5, rel=0.03)


def test_learns_a_holiday_dip_and_applies_it_to_a_future_holiday():
    holidays = [pd.Timestamp("2025-01-01") + timedelta(days=d) for d in range(20, 200, 28)]
    sales, dates = synth(200, lambda i, d: 50 if d in holidays else 100)
    future = dates[-1] + timedelta(days=4)
    cal = pd.DataFrame(
        {"type": "public_holiday", "label": None, "start_date": holidays + [future], "end_date": holidays + [future],
         "name": "Some holiday"}
    )
    fc = forecast_detail(sales, menu_of(), cal, dates[-1] + timedelta(days=1), 7)
    t = totals(fc)
    quiet = t[[d for d in t.index if abs((d - future).days) > 1]].mean()
    assert 0.75 < t[future] / quiet < 0.95  # learned (shrunk) dip, not zero and not 1
    assert fc.days.set_index("date").loc[future, "drivers"]["names"] == ["Some holiday"]
    assert fc.days.set_index("date").loc[dates[-1] + timedelta(days=1), "drivers"]["holiday_effect"] == 1.0


def test_period_switch_is_smoothed_across_the_boundary():
    spans = [("semester", 0, 100, 200), ("break", 100, 160, 100), ("semester", 160, 260, 200),
             ("break", 260, 320, 100), ("semester", 320, 400, 200)]
    level = lambda i: next(v for _, a, b, v in spans if a <= i < b)
    sales, dates = synth(317, lambda i, d: level(i))  # history ends 3 days before the break -> semester switch
    cal = pd.DataFrame(
        [{"type": "period", "label": lab, "start_date": dates[0] + timedelta(days=a),
          "end_date": dates[0] + timedelta(days=b - 1), "name": lab} for lab, a, b, _ in spans]
    )
    t = totals(forecast_detail(sales, menu_of(), cal, dates[-1] + timedelta(days=1), 7)).values
    assert (np.diff(t) > 0).all()  # gradual climb, not a step
    assert 100 < t[0] < 200 and 100 < t[-1] < 200
    assert t[0] == pytest.approx(122, abs=3) and t[-1] == pytest.approx(189, abs=3)  # blended +-4 days


def test_new_dish_is_forecast_from_recent_sales_only():
    def sold(i, d):
        return 100

    dates = pd.date_range("2025-01-01", periods=100)
    launch = dates[-1] - timedelta(days=19)
    rows = [(d, "A", 80.0) for d in dates] + [(d, "B", 20.0) for d in dates if d >= launch]
    sales = pd.DataFrame(rows, columns=["date", "item_id", "qty"])
    start = dates[-1] + timedelta(days=1)

    def b_fraction(launch_date):
        fc = forecast_detail(sales, menu_of(("A", "B"), {"B": launch_date}), NO_CAL, start, 1).lines
        return fc.set_index("item_id").qty["B"] / fc.qty.sum()

    as_new, as_old = b_fraction(launch), b_fraction(None)
    assert as_new > as_old + 0.02  # recent-only share is not diluted by the long zero history
    assert 0.14 < as_new < 0.155


def test_cold_start_with_little_history_is_flagged():
    sales, dates = synth(30, lambda i, d: 100)
    fc = forecast_detail(sales, menu_of(), NO_CAL, dates[-1] + timedelta(days=1), 3)
    assert all(d["cold_start"] for d in fc.days.drivers)
    assert totals(fc).values == pytest.approx([100, 100, 100], rel=0.01)
    sales, dates = synth(70, lambda i, d: 100)
    assert not forecast_detail(sales, menu_of(), NO_CAL, dates[-1] + timedelta(days=1), 3).days.drivers.iloc[0]["cold_start"]


def test_baselines_shapes_and_values():
    sales, dates = synth(60, lambda i, d: 10 + d.dayofweek)
    q = sales_to_wide(sales)
    origin = dates[-1] + timedelta(days=1)
    naive = naive_last_week(q, origin, 7)
    assert naive.index[0] == origin and naive.iloc[0, 0] == q.loc[origin - timedelta(days=7)].iloc[0]
    flat = flat_avg_4w(q, origin, 7)
    assert (flat.iloc[:, 0] == flat.iloc[0, 0]).all()
    assert flat.iloc[0, 0] == pytest.approx(q.iloc[-28:, 0].mean())


def test_calendar_state_combines_labels_and_marks_neighbours_of_holidays():
    cal = pd.DataFrame(
        [
            {"type": "period", "label": "break", "start_date": "2026-01-01", "end_date": "2026-01-10", "name": "Break"},
            {"type": "period", "label": "intake", "start_date": "2026-01-05", "end_date": "2026-01-07", "name": "Intake"},
            {"type": "public_holiday", "label": None, "start_date": "2026-01-20", "end_date": "2026-01-20", "name": "Holiday"},
            {"type": "local_event", "label": None, "start_date": "2026-01-25", "end_date": "2026-01-26", "name": "Fair"},
        ]
    )
    f = calendar_features(cal, pd.date_range("2026-01-01", "2026-01-31"))
    assert f.state["2026-01-02"] == "break" and f.state["2026-01-06"] == "break+intake" and f.state["2026-01-15"] == "normal"
    assert f.holiday["2026-01-19"] and f.holiday["2026-01-20"] and f.holiday["2026-01-21"] and not f.holiday["2026-01-22"]
    assert f.event["2026-01-25"] and f.event["2026-01-26"] and not f.event["2026-01-24"]
    assert f.names["2026-01-20"] == ("Holiday",) and f.names["2026-01-25"] == ("Fair",)


# ---------- real-world mess: closed days, long closures and dishes that left the menu ----------
def test_a_shop_closed_every_monday_still_gets_a_sensible_forecast():
    # Before the fix the Monday profile was 0, dividing by it made "not a number" and every forecast was NaN.
    sales, dates = synth(200, lambda i, d: 0 if d.dayofweek == 0 else 100)
    fc = forecast_detail(sales, menu_of(), NO_CAL, dates[-1] + timedelta(days=1), 7)
    t = totals(fc)
    assert np.isfinite(t.values).all() and np.isfinite(fc.lines.qty.values).all()
    for day, value in t.items():
        assert value == pytest.approx(0 if day.dayofweek == 0 else 100, abs=3)


def test_a_long_closure_just_before_the_plan_does_not_drag_the_forecast_to_zero():
    # nine closed days in a row (a festival break), then the plan for the reopening week
    sales, dates = synth(200, lambda i, d: 0 if i >= 191 else 100)
    t = totals(forecast_detail(sales, menu_of(), NO_CAL, dates[-1] + timedelta(days=1), 7))
    assert t.values == pytest.approx([100] * 7, rel=0.05)


def test_a_month_long_closure_does_not_make_the_whole_menu_look_discontinued():
    dates = pd.date_range("2025-01-01", periods=200)
    rows = [(d, item, qty if i < 170 else 0.0) for i, d in enumerate(dates) for item, qty in (("A", 70.0), ("B", 30.0))]
    sales = pd.DataFrame(rows, columns=["date", "item_id", "qty"])
    fc = forecast_detail(sales, menu_of(("A", "B")), NO_CAL, dates[-1] + timedelta(days=1), 3).lines
    by_item = fc.groupby("item_id").qty.sum()
    assert by_item["A"] > 0 and by_item["B"] > 0
    assert by_item["A"] / by_item.sum() == pytest.approx(0.7, abs=0.05)


def test_a_dish_that_left_the_menu_gets_no_forecast_but_a_rare_dish_keeps_a_share():
    dates = pd.date_range("2025-01-01", periods=200)
    rows = [(d, "A", 80.0) for d in dates]
    rows += [(d, "B", 20.0) for i, d in enumerate(dates) if i < 140]  # B stopped selling 60 days ago
    rows += [(d, "C", 1.0) for i, d in enumerate(dates) if i % 40 == 0 and i < 160]  # C is rare: 4 sales in 200 days
    sales = pd.DataFrame(rows, columns=["date", "item_id", "qty"])
    lines = forecast_detail(sales, menu_of(("A", "B", "C")), NO_CAL, dates[-1] + timedelta(days=1), 7).lines
    by_item = lines.groupby("item_id").qty.sum()
    assert by_item["B"] == 0  # it used to keep about 30% of its old share, so ingredients were bought for it
    assert by_item["C"] > 0  # no sale for 80 days is normal for a dish that sells every 40 days
    assert by_item["A"] == pytest.approx(7 * 80, rel=0.06)  # the shop now sells 80 a day: all of it is A
