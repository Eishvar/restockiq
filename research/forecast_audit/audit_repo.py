"""The same comparison, on the app's own synthetic data (data/*.csv): how do standard methods fare there?"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

import sys

sys.path[:0] = [os.path.dirname(os.path.abspath(__file__))]
import numpy as np
import pandas as pd

import audit_main as a

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
sales = pd.read_csv(f"{DATA}/daily_sales.csv", parse_dates=["date"])
menu = pd.read_csv(f"{DATA}/menu_items.csv", parse_dates=["launch_date"])
cal = pd.read_csv(f"{DATA}/calendar_events.csv", parse_dates=["start_date", "end_date"])
rec = pd.read_csv(f"{DATA}/recipes.csv")
ing = pd.read_csv(f"{DATA}/ingredients.csv")
q = sales.pivot_table(index="date", columns="item_id", values="qty", aggfunc="sum").fillna(0)
q = q.reindex(pd.date_range(q.index.min(), q.index.max()), fill_value=0)
bom = rec.pivot_table(index="item_id", columns="ingredient_id", values="qty_per_serving", aggfunc="sum").reindex(q.columns).fillna(0)
w = dict(q=q, q_true=q, menu=menu[["item_id", "category", "launch_date"]], cal=cal, bom=bom,
         ingr=ing[["ingredient_id", "shelf_life_days"]])
r = a.evaluate("repo_synthetic", 0, w)
print(f"seconds {r['seconds']}, planning days evaluated {r['n_eval_origins']}")
for m, v in r["acc"].items():
    if m == "oracle":
        continue
    print(f"{m:16s} WAPE {v['wape'] * 100:5.1f}%   bias {v['bias'] * 100:+5.1f}%   holiday/event days {v['wape_flagged'] * 100:5.1f}%   normal days {v['wape_normal'] * 100:5.1f}%")
print("buffer coverage on unseen days:", {k: round(v['actual'], 3) for k, v in r['cov'].items()}, "overall target/actual", round(r['cov_all']['target'], 3), round(r['cov_all']['actual'], 3))
print("shortage / leftover (% of need):", round(r['buf']['shortage_pct'] * 100, 2), round(r['buf']['leftover_pct'] * 100, 1))
