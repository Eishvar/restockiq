"""Audit 1: how accurate is the forecaster compared with standard methods, and do the safety buffers hold on unseen data?

Run:  auditenv\\Scripts\\python.exe audit_main.py [scenario ...]        (no arguments = all scenarios)

For each messy 'restaurant' (several random seeds each) it rolls through ~120 planning days of the last year. On each
day it forecasts the next 7 days using only the past, with the app's own engine and with standard alternatives,
then compares with what really sold. It also re-measures the safety buffers the way the app does (past forecast
errors, last 34 weeks) and checks how often the buffer really was enough on the days AFTER it was measured.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):  # one thread per worker
    os.environ[_v] = "1"

import math
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

from app.engine.forecast import calendar_for, flat_avg_4w, forecast_wide, menu_frame, naive_last_week  # noqa: E402
from app.engine.safety import SERVICE_LEVELS, safety_profiles  # noqa: E402
from world import make_world  # noqa: E402

HZ = 7
MODELS = ["app", "naive_last_week", "flat_4w", "sma4_weekday", "holt_winters", "ridge_calendar", "gbm_lags", "oracle"]

SCENARIOS = {
    "typical": dict(),
    "small_cafe": dict(base=60.0, dispersion=5.0),
    "closed_monday": dict(closed_weekday=0),
    "stockouts_gaps": dict(stockouts=True, missing_days_pct=0.03),
    "volatile": dict(day_shock_sd=0.15, holiday_sd=0.4, unknown_events_per_year=8, outliers_per_year=8),
    "owner_adds_periods": dict(labelled_periods=True),
    "fast_growth": dict(trend_per_year=0.45, level_shift=False),
    "calm": dict(day_shock_sd=0.03, unknown_events_per_year=1, outliers_per_year=1, holiday_sd=0.1, level_shift=False),
}


# ---------------------------------------------------------------------------------------------- helpers
def day_flags(cal: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
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


class Ctx:
    def __init__(self, w: dict):
        self.w = w
        self.q = w["q"]
        self.menu = menu_frame(w["menu"])
        self.calf = calendar_for(w["cal"], self.q, self.q.index.max() + pd.Timedelta(days=1), 14)
        self.tot = self.q.sum(axis=1)
        self.bom = w["bom"].reindex(self.q.columns).fillna(0)
        self.ing_ids = self.bom.columns.to_numpy()
        self.flags = day_flags(w["cal"], self.q.index)
        states = self.calf.state.reindex(self.q.index)
        self.state_dummies = pd.get_dummies(states, dtype=float)
        # features shared by the two regression-style models
        dow = pd.get_dummies(self.q.index.dayofweek, dtype=float)
        dow.index = self.q.index
        dow.columns = [f"dow{c}" for c in dow.columns]
        self.X_cal = pd.concat([dow, self.flags, self.state_dummies], axis=1)
        logT = np.log1p(self.tot)
        self.level_h = {h: logT.rolling(28, min_periods=14).mean().shift(h) for h in range(1, HZ + 1)}
        self.lags = pd.DataFrame(
            {
                "lag7": self.tot.shift(7), "lag14": self.tot.shift(14), "lag21": self.tot.shift(21), "lag28": self.tot.shift(28),
                "m28": self.tot.rolling(28, min_periods=14).mean().shift(7), "m7": self.tot.rolling(7, min_periods=4).mean().shift(7),
            }
        )


# ---------------------------------------------------------------------------------------------- the models
def m_sma4(c: Ctx, o):
    days = pd.date_range(o, periods=HZ)
    out = []
    for d in days:
        vals = [c.tot.get(d - pd.Timedelta(days=7 * k), np.nan) for k in range(1, 5)]
        out.append(np.nanmean(vals))
    return np.array(out)


def m_hw(c: Ctx, o):
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    y = c.tot[c.tot.index < o].iloc[-365:].values.astype(float)
    fit = ExponentialSmoothing(y, trend="add", damped_trend=True, seasonal="add", seasonal_periods=7,
                               initialization_method="estimated").fit()
    return np.clip(fit.forecast(HZ), 0, None)


def m_ridge(c: Ctx, o):
    from sklearn.linear_model import Ridge

    days = pd.date_range(o, periods=HZ)
    out = []
    train_idx = c.tot.index[(c.tot.index < o) & (c.tot.index >= o - pd.Timedelta(days=365))]
    for h in range(1, HZ + 1):
        X = c.X_cal.copy()
        X["level"] = c.level_h[h]
        Xt = X.loc[train_idx].dropna()
        y = np.log1p(c.tot.loc[Xt.index])
        cols = [k for k in Xt.columns if Xt[k].abs().sum() > 0]
        model = Ridge(alpha=1.0).fit(Xt[cols], y)
        xd = X.loc[[days[h - 1]], cols].fillna(0.0)
        out.append(float(np.expm1(model.predict(xd))[0]))
    return np.clip(np.array(out), 0, None)


def m_gbm(c: Ctx, o):
    from sklearn.ensemble import HistGradientBoostingRegressor

    X = pd.concat([c.X_cal, c.lags], axis=1)
    train_idx = c.tot.index[(c.tot.index < o) & (c.tot.index >= o - pd.Timedelta(days=500))]
    Xt = X.loc[train_idx].dropna()
    model = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.06, max_iter=120, min_samples_leaf=10,
                                          l2_regularization=1.0, random_state=0).fit(Xt, c.tot.loc[Xt.index])
    days = pd.date_range(o, periods=HZ)
    xd = X.loc[days].fillna(method=None) if False else X.loc[days]
    return np.clip(model.predict(xd.fillna(Xt.mean())), 0, None)


# ---------------------------------------------------------------------------------------------- one world
def run_world(args):
    name, seed, opts = args
    return evaluate(name, seed, make_world(seed=seed, **opts))


def evaluate(name, seed, w):
    t0 = time.time()
    c = Ctx(w)
    q, last = c.q, c.q.index.max()
    first = q.index[0]
    origins = [last - pd.Timedelta(days=HZ - 1) - pd.Timedelta(days=3 * i) for i in range(0, 700)]
    origins = sorted(o for o in origins if (o - first).days >= 56)
    eval_start = last - pd.Timedelta(days=364)
    eval_idx = [i for i, o in enumerate(origins) if o >= eval_start]

    n_o, n_i = len(origins), len(c.ing_ids)
    F = {m: np.full((n_o, HZ), np.nan) for m in MODELS}
    A = np.full((n_o, HZ), np.nan)
    FLAG = np.zeros((n_o, HZ), bool)  # day is a public holiday (+-1) or event
    ENEED_F = np.full((n_o, HZ, n_i), np.nan)  # forecast ingredient need over first h days, h=1..7
    ENEED_A = np.full((n_o, HZ, n_i), np.nan)
    bom_np = c.bom.to_numpy()

    for i, o in enumerate(origins):
        days = pd.date_range(o, periods=HZ)
        f, info = forecast_wide(q, c.menu.reindex(q.columns), c.calf, o, HZ)
        a = q.loc[days]
        A[i] = a.sum(axis=1).values
        F["app"][i] = f.sum(axis=1).values
        FLAG[i] = (c.calf.holiday.reindex(days) | c.calf.event.reindex(days)).values
        if "lam_total" in w:
            F["oracle"][i] = w["lam_total"].reindex(days).values
        cf, ca = f.cumsum().to_numpy() @ bom_np, a.cumsum().to_numpy() @ bom_np
        ENEED_F[i], ENEED_A[i] = cf, ca
        if i in eval_idx:
            F["naive_last_week"][i] = naive_last_week(q, o, HZ).sum(axis=1).values
            F["flat_4w"][i] = flat_avg_4w(q, o, HZ).sum(axis=1).values
            F["sma4_weekday"][i] = m_sma4(c, o)
            F["holt_winters"][i] = m_hw(c, o)
            F["ridge_calendar"][i] = m_ridge(c, o)
            F["gbm_lags"][i] = m_gbm(c, o)

    # ---- accuracy: WAPE and bias over the evaluation origins, per model, plus holiday/event days vs normal days
    ev = np.array(eval_idx)
    res = {"name": name, "seed": seed, "n_eval_origins": len(ev), "acc": {}}
    for m in MODELS:
        Fm, Am = F[m][ev], A[ev]
        ok = ~np.isnan(Fm)
        err = np.abs(Fm - Am)[ok]
        fl = FLAG[ev][ok]
        res["acc"][m] = dict(
            wape=err.sum() / Am[ok].sum(),
            bias=(Fm - Am)[ok].sum() / Am[ok].sum(),
            wape_h1=np.abs(Fm[:, 0] - Am[:, 0])[~np.isnan(Fm[:, 0])].sum() / Am[:, 0][~np.isnan(Fm[:, 0])].sum(),
            wape_h7=np.abs(Fm[:, 6] - Am[:, 6])[~np.isnan(Fm[:, 6])].sum() / Am[:, 6][~np.isnan(Fm[:, 6])].sum(),
            wape_flagged=err[fl].sum() / Am[ok][fl].sum() if fl.any() else np.nan,
            wape_normal=err[~fl].sum() / Am[ok][~fl].sum(),
        )

    # ---- buffers: re-measure them exactly as the app does at each planning day, test on that day's outcomes
    ingr = w["ingr"]
    err_rows = []
    for i, o in enumerate(origins):
        for h in range(HZ):
            fn, an = ENEED_F[i, h], ENEED_A[i, h]
            ok = fn > 0
            err_rows.append(pd.DataFrame({"ingredient_id": c.ing_ids[ok], "horizon": h + 1, "origin": o, "rel_err": an[ok] / fn[ok] - 1}))
    errors = pd.concat(err_rows, ignore_index=True)
    cover, rows_out = [], []
    for i in eval_idx:
        t = origins[i]
        known = errors[(errors.origin <= t - pd.Timedelta(days=HZ)) & (errors.origin >= t - pd.Timedelta(days=34 * 7))]
        prof = safety_profiles(known, ingr, "balanced")
        buf = prof.pivot(index="ingredient_id", columns="horizon", values="buffer").reindex(c.ing_ids)
        sl = prof.pivot(index="ingredient_id", columns="horizon", values="service_level").reindex(c.ing_ids)
        method = prof.pivot(index="ingredient_id", columns="horizon", values="method").reindex(c.ing_ids)
        for h in range(HZ):
            fn, an = ENEED_F[i, h], ENEED_A[i, h]
            ok = fn > 0
            b = buf[h + 1].to_numpy()[ok]
            rows_out.append(
                pd.DataFrame(
                    {
                        "h": h + 1, "sl": sl[h + 1].to_numpy()[ok], "buffer": b, "default": (method[h + 1].to_numpy()[ok] == "default"),
                        "fn": fn[ok], "an": an[ok], "covered": an[ok] <= fn[ok] * (1 + b) + 1e-9,
                        "short": np.maximum(0, an[ok] - fn[ok] * (1 + b)), "left": np.maximum(0, fn[ok] * (1 + b) - an[ok]),
                    }
                )
            )
    cov = pd.concat(rows_out, ignore_index=True)
    res["cov"] = {
        f"sl{s:.2f}": dict(target=s, actual=float(cov[np.isclose(cov.sl, s)].covered.mean()), n=int(np.isclose(cov.sl, s).sum()))
        for s in sorted({0.7, 0.8, 0.9, 0.95, 0.98}) if np.isclose(cov.sl, s).any()
    }
    res["cov_all"] = dict(target=float(cov.sl.mean()), actual=float(cov.covered.mean()))
    res["cov_h"] = {int(h): float(g.covered.mean()) for h, g in cov.groupby("h")}
    res["buf"] = dict(mean_buffer=float(cov.buffer.mean()), shortage_pct=float(cov.short.sum() / cov.an.sum()),
                      leftover_pct=float(cov.left.sum() / cov.an.sum()), default_share=float(cov.default.mean()))
    res["seconds"] = round(time.time() - t0, 1)
    return res


# ---------------------------------------------------------------------------------------------- driver
def main():
    names = sys.argv[1:] or list(SCENARIOS)
    seeds = [int(s) for s in os.environ.get("AUDIT_SEEDS", "0,1,2").split(",")]
    jobs = [(n, s, SCENARIOS[n]) for n in names for s in seeds]
    t0 = time.time()
    results = []
    with ProcessPoolExecutor(max_workers=7) as pool:
        for r in pool.map(run_world, jobs):
            results.append(r)
            print(f"  done {r['name']} seed {r['seed']} ({r['seconds']}s, {len(results)}/{len(jobs)})", flush=True)
    print(f"\nfinished {len(jobs)} worlds in {time.time() - t0:.0f}s\n")

    import json

    with open(os.path.join(HERE, "results_main.json"), "w") as f:
        json.dump(results, f, default=float)

    print("== Daily-total accuracy (WAPE, lower is better; averaged over 3 random restaurants per row) ==")
    head = f"{'scenario':20s}" + "".join(f"{m[:11]:>12s}" for m in MODELS)
    print(head)
    for n in names:
        rs = [r for r in results if r["name"] == n]
        print(f"{n:20s}" + "".join(f"{np.mean([r['acc'][m]['wape'] for r in rs]) * 100:11.1f}%" for m in MODELS))
    print("\n== Bias (forecast minus actual, % of sales; negative = under-forecasting) ==")
    for n in names:
        rs = [r for r in results if r["name"] == n]
        print(f"{n:20s}" + "".join(f"{np.mean([r['acc'][m]['bias'] for r in rs]) * 100:11.1f}%" for m in MODELS))
    print("\n== The app's WAPE on holiday/event days vs normal days, and by horizon ==")
    for n in names:
        rs = [r for r in results if r["name"] == n]
        g = lambda k, m="app": np.nanmean([r["acc"][m][k] for r in rs]) * 100  # noqa: E731
        print(f"{n:20s} normal {g('wape_normal'):5.1f}%  flagged {g('wape_flagged'):5.1f}%  | day+1 {g('wape_h1'):5.1f}%  day+7 {g('wape_h7'):5.1f}%")
    print("\n== Safety buffers on UNSEEN days: target service level vs how often the buffer was really enough ==")
    for n in names:
        rs = [r for r in results if r["name"] == n]
        parts = []
        for key in ("sl0.80", "sl0.90", "sl0.95"):
            vals = [r["cov"][key]["actual"] for r in rs if key in r["cov"]]
            if vals:
                parts.append(f"{key[2:]}: {np.mean(vals) * 100:5.1f}%")
        allv = np.mean([r["cov_all"]["actual"] for r in rs]) * 100
        tgt = np.mean([r["cov_all"]["target"] for r in rs]) * 100
        b = {k: np.mean([r["buf"][k] for r in rs]) * 100 for k in ("mean_buffer", "shortage_pct", "leftover_pct")}
        print(f"{n:20s} targets-avg {tgt:5.1f}% -> actual {allv:5.1f}% | " + "  ".join(parts)
              + f" | mean buffer {b['mean_buffer']:4.1f}%  short {b['shortage_pct']:4.1f}%  left {b['leftover_pct']:5.1f}% of need")


if __name__ == "__main__":
    main()
