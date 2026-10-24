"""Audit 5: the first weeks. How should a short history's weekday pattern be treated?"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

import sys
import warnings
from concurrent.futures import ProcessPoolExecutor

sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")]
warnings.simplefilter("ignore")
import numpy as np
import pandas as pd

from app.engine.forecast import calendar_for, menu_frame
from audit_variants import flags_for
from variant import forecast_v
from world import make_world

HZ = 7
LENGTHS = [14, 21, 28, 42, 55, 70]
SETTINGS = {"today (weekday pattern as measured)": None, "shrink k=2": 2.0, "shrink k=4": 4.0, "shrink k=8": 8.0, "no weekday pattern (flat)": float("inf")}
import json as _json

KINDS =_json.loads(os.environ["COLD_KINDS"]) if os.environ.get("COLD_KINDS") else {"typical": dict(), "small_cafe": dict(base=60.0, dispersion=5.0), "owner_adds_periods": dict(labelled_periods=True), "calm": dict(day_shock_sd=0.03, unknown_events_per_year=1, outliers_per_year=1, level_shift=False)}


def job(args):
    name, seed = args
    w = make_world(seed=seed, **KINDS[name])
    q = w["q"]
    menu = menu_frame(w["menu"]).reindex(q.columns)
    calf = calendar_for(w["cal"], q, q.index.max() + pd.Timedelta(days=1), 14)
    flags = flags_for(w["cal"], calf.index)
    bom = w["bom"].reindex(q.columns).fillna(0).to_numpy()
    last = q.index.max()
    origins = [last - pd.Timedelta(days=HZ - 1) - pd.Timedelta(days=3 * i) for i in range(0, 100)]
    out = {}
    for L in LENGTHS:
        for sname, k in SETTINGS.items():
            e = a = ei = ai = 0.0
            for o in origins:
                qq = q.loc[q.index >= o - pd.Timedelta(days=L)]
                f, _ = forecast_v(qq, menu, calf, o, HZ, flags=flags, robust=True, drop_dead_dishes=True, cold_shrink_k=k)
                act = q.loc[pd.date_range(o, periods=HZ)]
                ft, at = f.sum(axis=1).values, act.sum(axis=1).values
                e += np.abs(ft - at).sum(); a += at.sum()
                cf, ca = f.cumsum().to_numpy() @ bom, act.cumsum().to_numpy() @ bom
                ei += np.abs(cf[2] - ca[2]).sum(); ai += ca[2].sum()
            out[(L, sname)] = (e / a, ei / ai)
    return out


if __name__ == "__main__":
    jobs = [(n, s) for n in KINDS for s in (0, 1, 2)]
    with ProcessPoolExecutor(max_workers=7) as pool:
        res = list(pool.map(job, jobs))
    print("Error of daily totals / 3-day ingredient needs (average of 12 simulated restaurants)")
    print(f"{'days of history':>16s}" + "".join(f"{s[:24]:>27s}" for s in SETTINGS))
    for L in LENGTHS:
        row = f"{L:16d}"
        for s in SETTINGS:
            t = np.mean([r[(L, s)][0] for r in res]) * 100
            i = np.mean([r[(L, s)][1] for r in res]) * 100
            row += f"{t:15.1f}% /{i:6.1f}%  "
        print(row)
