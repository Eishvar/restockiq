"""Audit 2: which parts of the forecaster earn their place, and which small changes would make it better or safer?

Each variant is the app's forecaster with ONE switch changed. Scores are on the last 52 weeks of each simulated restaurant,
planning every 3 days, using only the past. Two scores: daily-total error and ingredient-need error (the one that
decides what to buy), both as WAPE (total absolute error / total actual; lower is better).
"""
import json
import os

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_v] = '1'

import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")
sys.path[:0] = [HERE, BACKEND]
warnings.simplefilter("ignore")

from app.engine.forecast import calendar_for, forecast_wide, menu_frame  # noqa: E402
from variant import forecast_v  # noqa: E402
from world import make_world  # noqa: E402

HZ = 7
SCENARIOS = {
    "typical": dict(),
    "small_cafe": dict(base=60.0, dispersion=5.0),
    "closed_monday": dict(closed_weekday=0),
    "stockouts_gaps": dict(stockouts=True, missing_days_pct=0.03),
    "volatile": dict(day_shock_sd=0.15, holiday_sd=0.4, unknown_events_per_year=8, outliers_per_year=8),
    "owner_adds_periods": dict(labelled_periods=True),
    "fast_growth": dict(trend_per_year=0.45, level_shift=False),
    "calm": dict(day_shock_sd=0.03, unknown_events_per_year=1, outliers_per_year=1, holiday_sd=0.1, level_shift=False),
    "closing_holidays": dict(holiday_mean=0.3, holiday_sd=0.3),
    "menu_churn": dict(new_dishes_per_year=6, dropped_dishes_per_year=6),
}

VARIANTS = {
    "engine (today)": dict(),
    "robust": dict(robust=True),
    "robust+drop_dead": dict(robust=True, drop_dead_dishes=True),
    "level window 7d": dict(robust=True, strength_window=7),
    "level window 10d": dict(robust=True, strength_window=10),
    "level window 21d": dict(robust=True, strength_window=21),
    "level window 28d": dict(robust=True, strength_window=28),
    "level = mean 14d": dict(robust=True, strength_stat="mean"),
    "level = trimmed 14d": dict(robust=True, strength_stat="trim"),
    "no boundary blur": dict(robust=True, smooth_days=0),
    "blur 2d": dict(robust=True, smooth_days=2),
    "blur 7d": dict(robust=True, smooth_days=7),
    "shrink k=1": dict(robust=True, shrink_k=1),
    "shrink k=6": dict(robust=True, shrink_k=6),
    "holiday before/on/after": dict(robust=True, split_holiday=True),
    "no holiday effect": dict(robust=True, use_holiday=False),
    "no event effect": dict(robust=True, use_event=False),
    "dish share 56d": dict(robust=True, share_window=56),
    "dish share 100% recent": dict(robust=True, share_recent=1.0),
    "dish share 50% recent": dict(robust=True, share_recent=0.5),
}


_FINAL = dict(robust=True, drop_dead_dishes=True)  # = the engine after today's two fixes
VARIANT_SETS = {
    "all": VARIANTS,
    "final": {
        "engine (today)": dict(),
        "robust": dict(robust=True),
        "fixed engine": dict(_FINAL),
        "fixed + level 21d": dict(_FINAL, strength_window=21),
        "fixed + level 28d": dict(_FINAL, strength_window=28),
        "fixed + level trimmed": dict(_FINAL, strength_stat="trim"),
        "fixed + level 21d trimmed": dict(_FINAL, strength_window=21, strength_stat="trim"),
        "fixed + dish share 100% recent": dict(_FINAL, share_recent=1.0),
        "fixed + dish share 85% recent": dict(_FINAL, share_recent=0.85),
        "fixed + holiday before/on/after": dict(_FINAL, split_holiday=True),
    },
}
VARIANTS = VARIANT_SETS[os.environ.get("VARIANT_SET", "all")]


def flags_for(cal, index):
    f = pd.DataFrame(0.0, index=index, columns=["hol", "hol_before", "hol_after", "event"])
    for r in cal.itertuples(index=False):
        s, e = pd.Timestamp(r.start_date), pd.Timestamp(r.end_date)
        if r.type == "public_holiday":
            f.loc[(index >= s) & (index <= e), "hol"] = 1
            f.loc[index == s - pd.Timedelta(days=1), "hol_before"] = 1
            f.loc[index == e + pd.Timedelta(days=1), "hol_after"] = 1
        elif r.type == "local_event":
            f.loc[(index >= s) & (index <= e), "event"] = 1
    return f


def run_world(args):
    name, seed, opts = args
    w = make_world(seed=seed, **opts)
    q = w["q"]
    menu = menu_frame(w["menu"]).reindex(q.columns)
    calf = calendar_for(w["cal"], q, q.index.max() + pd.Timedelta(days=1), 14)
    flags = flags_for(w["cal"], calf.index)
    bom = w["bom"].reindex(q.columns).fillna(0).to_numpy()
    last = q.index.max()
    origins = [last - pd.Timedelta(days=HZ - 1) - pd.Timedelta(days=3 * i) for i in range(0, 120)]
    out = {"name": name, "seed": seed, "v": {}}
    for vname, kw in VARIANTS.items():
        err_t = act_t = err_i3 = act_i3 = err_i7 = act_i7 = bias_t = 0.0
        nan = 0
        for o in origins:
            days = pd.date_range(o, periods=HZ)
            try:
                f, tot = forecast_v(q, menu, calf, o, HZ, flags=flags, **kw)
            except Exception:  # noqa: BLE001
                nan += 1
                continue
            if not np.isfinite(f.values).all():
                nan += 1
                continue
            a = q.loc[days]
            ft, at = f.sum(axis=1).values, a.sum(axis=1).values
            err_t += np.abs(ft - at).sum(); act_t += at.sum(); bias_t += (ft - at).sum()
            cf_, ca_ = f.cumsum().to_numpy() @ bom, a.cumsum().to_numpy() @ bom
            err_i3 += np.abs(cf_[2] - ca_[2]).sum(); act_i3 += ca_[2].sum()
            err_i7 += np.abs(cf_[6] - ca_[6]).sum(); act_i7 += ca_[6].sum()
        ok = act_t > 0
        out["v"][vname] = dict(
            total=err_t / act_t if ok else np.nan, bias=bias_t / act_t if ok else np.nan,
            ing3=err_i3 / act_i3 if ok else np.nan, ing7=err_i7 / act_i7 if ok else np.nan,
            failed=nan,
        )
    return out


def main():
    names = sys.argv[1:] or list(SCENARIOS)
    jobs = [(n, s, SCENARIOS[n]) for n in names for s in (0, 1, 2)]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=7) as pool:
        results = list(pool.map(run_world, jobs))
    print(f"finished {len(jobs)} worlds x {len(VARIANTS)} variants in {time.time() - t0:.0f}s\n")
    with open(os.path.join(HERE, "results_variants.json"), "w") as f:
        json.dump(results, f, default=float)

    def mean(metric, vname, scen=None):
        vals = [r["v"][vname][metric] for r in results if scen is None or r["name"] == scen]
        return float(np.nanmean(vals)) if not all(np.isnan(vals)) else float("nan")

    base = "fixed engine" if "fixed engine" in VARIANTS else "robust"
    print(f"== All {len(names)} kinds of restaurant averaged: error of daily totals and of ingredient needs ==")
    print(f"{'variant':26s}{'total WAPE':>11s}{'ingr 3-day':>11s}{'ingr 7-day':>11s}{'change vs robust (total / ingr3)':>36s}{'failed forecasts':>18s}")
    for v in VARIANTS:
        fails = sum(r["v"][v]["failed"] for r in results)
        t, i3, i7 = mean("total", v), mean("ing3", v), mean("ing7", v)
        dt, di = t - mean("total", base), i3 - mean("ing3", base)
        print(f"{v:26s}{t * 100:10.2f}%{i3 * 100:10.2f}%{i7 * 100:10.2f}%{dt * 100:+16.2f} pts /{di * 100:+7.2f} pts{fails:18d}")

    print("\n== Per kind of restaurant: daily-total WAPE, today's engine vs the robust version ==")
    for n in names:
        print(f"{n:20s} engine {mean('total', 'engine (today)', n) * 100:6.2f}%   robust {mean('total', 'robust', n) * 100:6.2f}%   "
              f"+drop_dead {mean('total', 'robust+drop_dead', n) * 100:6.2f}% | ingr3 engine {mean('ing3', 'engine (today)', n) * 100:6.2f}%  "
              f"robust {mean('ing3', 'robust', n) * 100:6.2f}%  +drop_dead {mean('ing3', 'robust+drop_dead', n) * 100:6.2f}%  "
              f"| failed forecasts (engine): {sum(r['v']['engine (today)']['failed'] for r in results if r['name'] == n)}")

    print("\n== Where do the switches matter most? change in daily-total WAPE vs 'robust', by restaurant type (points) ==")
    print(f"{'variant':26s}" + "".join(f"{n[:10]:>11s}" for n in names))
    for v in VARIANTS:
        if v in ("engine (today)", "robust"):
            continue
        print(f"{v:26s}" + "".join(f"{(mean('total', v, n) - mean('total', base, n)) * 100:+10.2f} " for n in names))


if __name__ == "__main__":
    main()
