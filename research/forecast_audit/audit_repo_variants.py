"""The same one-switch variants, on the app's own synthetic data (data/*.csv)."""
import os

os.environ["VARIANT_SET"] = "final"
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

import sys

sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")]
import warnings

warnings.simplefilter("ignore")
import numpy as np
import pandas as pd

import audit_variants as av
from app.engine.forecast import calendar_for, menu_frame
from variant import forecast_v

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
sales = pd.read_csv(f"{DATA}/daily_sales.csv", parse_dates=["date"])
menu_df = pd.read_csv(f"{DATA}/menu_items.csv", parse_dates=["launch_date"])
cal = pd.read_csv(f"{DATA}/calendar_events.csv", parse_dates=["start_date", "end_date"])
rec = pd.read_csv(f"{DATA}/recipes.csv")
q = sales.pivot_table(index="date", columns="item_id", values="qty", aggfunc="sum").fillna(0)
q = q.reindex(pd.date_range(q.index.min(), q.index.max()), fill_value=0)
menu = menu_frame(menu_df[["item_id", "category", "launch_date"]]).reindex(q.columns)
calf = calendar_for(cal, q, q.index.max() + pd.Timedelta(days=1), 14)
flags = av.flags_for(cal, calf.index)
bom = rec.pivot_table(index="item_id", columns="ingredient_id", values="qty_per_serving", aggfunc="sum").reindex(q.columns).fillna(0).to_numpy()
last, HZ = q.index.max(), 7
origins = [last - pd.Timedelta(days=HZ - 1) - pd.Timedelta(days=3 * i) for i in range(0, 100)]  # the last ~300 days
print(f"{'variant':34s}{'total WAPE':>11s}{'ingr 3-day':>11s}{'ingr 7-day':>11s}")
rows = {}
for name, kw in av.VARIANTS.items():
    et = at = e3 = a3 = e7 = a7 = 0.0
    for o in origins:
        f, _ = forecast_v(q, menu, calf, o, HZ, flags=flags, **kw)
        a = q.loc[pd.date_range(o, periods=HZ)]
        ft, atot = f.sum(axis=1).values, a.sum(axis=1).values
        et += np.abs(ft - atot).sum(); at += atot.sum()
        cf, ca = f.cumsum().to_numpy() @ bom, a.cumsum().to_numpy() @ bom
        e3 += np.abs(cf[2] - ca[2]).sum(); a3 += ca[2].sum(); e7 += np.abs(cf[6] - ca[6]).sum(); a7 += ca[6].sum()
    rows[name] = (et / at, e3 / a3, e7 / a7)
    print(f"{name:34s}{et / at * 100:10.2f}%{e3 / a3 * 100:10.2f}%{e7 / a7 * 100:10.2f}%", flush=True)
