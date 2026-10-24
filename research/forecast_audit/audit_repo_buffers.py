"""Buffer calibration on the app's own one-year synthetic data: all planning days after day 62, and only the last 5 months."""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

import sys

sys.path[:0] = [os.path.dirname(os.path.abspath(__file__))]
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

import audit_buffers as ab

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")


def world():
    sales = pd.read_csv(f"{DATA}/daily_sales.csv", parse_dates=["date"])
    menu = pd.read_csv(f"{DATA}/menu_items.csv", parse_dates=["launch_date"])
    cal = pd.read_csv(f"{DATA}/calendar_events.csv", parse_dates=["start_date", "end_date"])
    rec = pd.read_csv(f"{DATA}/recipes.csv")
    ing = pd.read_csv(f"{DATA}/ingredients.csv")
    q = sales.pivot_table(index="date", columns="item_id", values="qty", aggfunc="sum").fillna(0)
    q = q.reindex(pd.date_range(q.index.min(), q.index.max()), fill_value=0)
    bom = rec.pivot_table(index="item_id", columns="ingredient_id", values="qty_per_serving", aggfunc="sum").reindex(q.columns).fillna(0)
    return dict(q=q, menu=menu[["item_id", "category", "launch_date"]], cal=cal, bom=bom, ingr=ing[["ingredient_id", "shelf_life_days"]])


def job(eval_days):
    return ab.evaluate(f"repo_last_{eval_days}d", 0, world(), eval_days=eval_days)


if __name__ == "__main__":
    with ProcessPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(job, [364, 150]))
    for r in results:
        print(f"\n== {r['name']}: how often was the buffer enough on unseen days? ==")
        print(f"{'method':12s}{'cover@80':>9s}{'cover@90':>9s}{'cover@95':>9s}{'shortage':>10s}{'leftover':>10s}{'pinball':>9s}")
        for m, v in r["m"].items():
            c = lambda s: v["cov"].get(s, float("nan")) * 100  # noqa: E731
            print(f"{m:12s}{c(0.8):8.1f}%{c(0.9):8.1f}%{c(0.95):8.1f}%{v['short'] * 100:9.2f}%{v['left'] * 100:9.1f}%{v['pinball'] * 1000:9.2f}")
        print("coverage by horizon (today's method):", {h + 1: round(x * 100, 1) for h, x in r["m"]["today"]["cov_h"].items()})
        print("later-start windows:", {k: round(x * 100, 1) for k, x in r["window_cov"].items() if k.startswith("L3")})
        print("match with app's safety_profiles:", r["match"])
        print("error correlation between 7-day plans 3, 6, 9, 12 days apart:", [round(x, 2) for x in r["autocorr_h7"]],
              "| planning days in the 34-week calibration window:", r["n_calibration_origins"])
