"""Audit 4: how much sales history does the forecaster need? Same planning days, but the model only sees the last L days."""
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

from app.engine.forecast import calendar_for, flat_avg_4w, forecast_wide, menu_frame
from world import make_world

HZ = 7
LENGTHS = [14, 28, 56, 90, 180, 365, 540]
KINDS = {"typical": dict(), "small_cafe": dict(base=60.0, dispersion=5.0), "owner_adds_periods": dict(labelled_periods=True)}


def job(args):
    name, seed = args
    w = make_world(seed=seed, **KINDS[name])
    q = w["q"]
    menu = menu_frame(w["menu"]).reindex(q.columns)
    calf = calendar_for(w["cal"], q, q.index.max() + pd.Timedelta(days=1), 14)
    bom = w["bom"].reindex(q.columns).fillna(0).to_numpy()
    last = q.index.max()
    origins = [last - pd.Timedelta(days=HZ - 1) - pd.Timedelta(days=3 * i) for i in range(0, 120)]
    out = {}
    for L in LENGTHS:
        e = a = ei = ai = ef = 0.0
        for o in origins:
            qq = q.loc[q.index >= o - pd.Timedelta(days=L)]
            f, _ = forecast_wide(qq, menu, calf, o, HZ)
            act = q.loc[pd.date_range(o, periods=HZ)]
            ft, at = f.sum(axis=1).values, act.sum(axis=1).values
            e += np.abs(ft - at).sum(); a += at.sum()
            ef += np.abs(flat_avg_4w(qq, o, HZ).sum(axis=1).values - at).sum()
            cf, ca = f.cumsum().to_numpy() @ bom, act.cumsum().to_numpy() @ bom
            ei += np.abs(cf[2] - ca[2]).sum(); ai += ca[2].sum()
        out[L] = (e / a, ef / a, ei / ai)
    return name, seed, out


if __name__ == "__main__":
    jobs = [(n, s) for n in KINDS for s in (0, 1, 2)]
    with ProcessPoolExecutor(max_workers=6) as pool:
        res = list(pool.map(job, jobs))
    print("History the model can see  |  daily-total error, app model   |  plain 4-week average   |  3-day ingredient-need error")
    for L in LENGTHS:
        t = np.mean([r[2][L][0] for r in res]) * 100
        f = np.mean([r[2][L][1] for r in res]) * 100
        i = np.mean([r[2][L][2] for r in res]) * 100
        print(f"{L:4d} days (~{L / 30.4:4.1f} months) |{t:24.1f}%{f:22.1f}%{i:24.1f}%")
