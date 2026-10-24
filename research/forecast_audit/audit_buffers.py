"""Audit 3: the safety buffer. Is 'the 90% buffer enough 90% of the time' true on days it was NOT measured on,
and can standard statistical fixes make it more reliable?

Every method re-measures the buffer at each planning day from errors that were already known at that time
(forecast origins at least 7 days old, within the last 34 weeks), then is judged on that day's real outcome.
Scores: coverage vs target, shortage and leftover as % of need, and the pinball (quantile) loss, which rewards a buffer
that is both calibrated and not wastefully large.
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
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")]
warnings.simplefilter("ignore")

from app.engine.forecast import calendar_for, menu_frame  # noqa: E402
from app.engine.safety import SERVICE_LEVELS, safety_profiles  # noqa: E402
from audit_variants import SCENARIOS, flags_for  # noqa: E402
from variant import forecast_v  # noqa: E402
from world import make_world  # noqa: E402

HZ = 7
SL = SERVICE_LEVELS["balanced"]


def service(shelf):
    return SL[2] if shelf >= 30 else SL[1] if shelf >= 7 else SL[0]


def wquantile(vals, w, tau):
    order = np.argsort(vals)
    v, ww = vals[order], w[order]
    c = np.cumsum(ww) / ww.sum()
    return v[min(np.searchsorted(c, tau), len(v) - 1)]


def buffers(method, E, orig_days, t_day, sl, ing_n):
    """Buffer fraction for every (h, ingredient) at planning day t_day, from errors known by then."""
    known = (orig_days <= t_day - 7) & (orig_days >= t_day - 34 * 7)
    out = np.full((HZ, ing_n), 0.15)
    pool = {}
    if method == "pooled":  # pooled quantile per horizon and service level across all ingredients
        for h in range(HZ):
            for s in set(sl):
                cols = [i for i in range(ing_n) if sl[i] == s]
                pool[(h, s)] = np.nanquantile(E[known][:, h, :][:, cols], s) if np.isfinite(E[known][:, h, :][:, cols]).sum() > 30 else 0.15
    age = (t_day - orig_days[known]).astype(float)
    for h in range(HZ):
        for i in range(ing_n):
            v = E[known, h, i]
            ok = np.isfinite(v)
            n = int(ok.sum())
            if n < 12:
                continue
            vv, tau = v[ok], sl[i]
            if method == "today":
                b = np.quantile(vv, tau)
            elif method == "conformal":
                k = min(n, int(np.ceil((n + 1) * tau)))
                b = np.sort(vv)[k - 1]
            elif method == "recency":
                b = wquantile(vv, 0.5 ** (age[ok] / 70.0), tau)
            elif method == "pooled":
                q_i = np.quantile(vv, tau)
                n_eff = n / 3.0  # neighbouring planning days share most of their outcomes
                lam = n_eff / (n_eff + 20.0)
                b = lam * q_i + (1 - lam) * pool[(h, tau)]
            elif method == "recency+pooled":
                q_i = wquantile(vv, 0.5 ** (age[ok] / 70.0), tau)
                n_eff = n / 3.0
                lam = n_eff / (n_eff + 20.0)
                b = lam * q_i + (1 - lam) * pool.get((h, tau), q_i) if pool else q_i
            else:
                raise ValueError(method)
            out[h, i] = b
    return np.clip(out, 0.0, 0.60)


METHODS = ["today", "conformal", "recency", "pooled"]


def run_world(args):
    name, seed, opts = args
    return evaluate(name, seed, make_world(seed=seed, **opts))


def evaluate(name, seed, w, eval_days=364):
    q = w["q"]
    menu = menu_frame(w["menu"]).reindex(q.columns)
    calf = calendar_for(w["cal"], q, q.index.max() + pd.Timedelta(days=1), 14)
    flags = flags_for(w["cal"], calf.index)
    bom = w["bom"].reindex(q.columns).fillna(0).to_numpy()
    n_i = bom.shape[1]
    last, first = q.index.max(), q.index.min()
    origins = sorted(o for o in (last - pd.Timedelta(days=HZ - 1) - pd.Timedelta(days=3 * i) for i in range(700)) if (o - first).days >= 56)
    E = np.full((len(origins), HZ, n_i), np.nan)
    FN = np.full_like(E, np.nan)
    AN = np.full_like(E, np.nan)
    FD = np.full_like(E, np.nan)  # per-day forecast need (day 0..6 after the planning day)
    AD = np.full_like(E, np.nan)
    for k, o in enumerate(origins):
        f, _ = forecast_v(q, menu, calf, o, HZ, flags=flags, robust=True, drop_dead_dishes=True)
        a = q.loc[pd.date_range(o, periods=HZ)]
        fn, an = f.cumsum().to_numpy() @ bom, a.cumsum().to_numpy() @ bom
        ok = fn > 0
        E[k][ok] = an[ok] / fn[ok] - 1
        FN[k], AN[k] = fn, an
        FD[k], AD[k] = f.to_numpy() @ bom, a.to_numpy() @ bom
    orig_days = np.array([(o - first).days for o in origins])
    sl = np.array([service(s) for s in w["ingr"].shelf_life_days])
    eval_idx = [k for k, o in enumerate(origins) if o >= last - pd.Timedelta(days=eval_days)]

    # sanity: our re-implementation of 'today' equals the app's own safety_profiles on one planning day
    t = eval_idx[len(eval_idx) // 2]
    rows = []
    for k, o in enumerate(origins):
        if orig_days[k] <= orig_days[t] - 7 and orig_days[k] >= orig_days[t] - 238:
            for h in range(HZ):
                ok = np.isfinite(E[k, h])
                rows.append(pd.DataFrame({"ingredient_id": w["ingr"].ingredient_id.values[ok], "horizon": h + 1, "origin": o, "rel_err": E[k, h][ok]}))
    prof = safety_profiles(pd.concat(rows), w["ingr"], "balanced")
    mine = buffers("today", E, orig_days, orig_days[t], sl, n_i)
    theirs = prof.pivot(index="ingredient_id", columns="horizon", values="buffer").to_numpy().T
    match = float(np.abs(mine - theirs).max())

    res = {"name": name, "seed": seed, "match": match, "m": {}}
    for m in METHODS:
        cov = {s: [] for s in sorted(set(sl))}
        short = left = need = pin = cnt = 0.0
        cov_h = {h: [] for h in range(HZ)}
        for k in eval_idx:
            b = buffers(m, E, orig_days, orig_days[k], sl, n_i)
            for h in range(HZ):
                ok = np.isfinite(E[k, h])
                covered = E[k, h][ok] <= b[h][ok] + 1e-12
                for s in cov:
                    cov[s].extend(covered[sl[ok] == s].tolist())
                cov_h[h].extend(covered.tolist())
                fn, an = FN[k, h][ok], AN[k, h][ok]
                short += np.maximum(0, an - fn * (1 + b[h][ok])).sum()
                left += np.maximum(0, fn * (1 + b[h][ok]) - an).sum()
                need += an.sum()
                e, tau = E[k, h][ok], sl[ok]
                d = e - b[h][ok]
                pin += np.where(d >= 0, tau * d, (tau - 1) * d).sum()
                cnt += ok.sum()
        res["m"][m] = dict(cov={float(s): float(np.mean(v)) for s, v in cov.items() if v}, short=short / need, left=left / need, pinball=pin / cnt,
                           cov_h={h: float(np.mean(v)) for h, v in cov_h.items()})
    # a purchase window that starts later in the plan (days s..s+L-1) still uses the buffer measured for 'the first L days'
    win = {}
    for L in (2, 3, 4):
        for s in range(0, HZ - L + 1):
            hits = []
            for k in eval_idx:
                b = buffers("today", E, orig_days, orig_days[k], sl, n_i)[L - 1]
                wf, wa = FD[k, s : s + L].sum(axis=0), AD[k, s : s + L].sum(axis=0)
                ok = wf > 0
                hits.extend((wa[ok] <= wf[ok] * (1 + b[ok]) + 1e-9).tolist())
            win[f"L{L}_start{s}"] = float(np.mean(hits))
    res["window_cov"] = win
    # how independent are neighbouring planning days? lag correlation of the errors
    z = np.nanmean(E[:, 2, :], axis=1)
    z = z[np.isfinite(z)]
    ac = [float(np.corrcoef(z[:-L], z[L:])[0, 1]) for L in (1, 2, 3, 4)]
    res["autocorr_by_3day_lag"] = ac
    z7 = np.nanmean(E[:, 6, :], axis=1)
    z7 = z7[np.isfinite(z7)]
    res["autocorr_h7"] = [float(np.corrcoef(z7[:-L], z7[L:])[0, 1]) for L in (1, 2, 3, 4)]
    res["n_calibration_origins"] = int(((orig_days <= orig_days[eval_idx[-1]] - 7) & (orig_days >= orig_days[eval_idx[-1]] - 238)).sum())
    return res


def main():
    names = sys.argv[1:] or list(SCENARIOS)
    seeds = [int(s) for s in os.environ.get("AUDIT_SEEDS", "0,1,2").split(",")]
    jobs = [(n, s, SCENARIOS[n]) for n in names for s in seeds]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=7) as pool:
        results = list(pool.map(run_world, jobs))
    print(f"finished {len(jobs)} worlds in {time.time() - t0:.0f}s; largest gap between my re-implementation and the app's safety_profiles: "
          f"{max(r['match'] for r in results):.2e}\n")
    with open(os.path.join(HERE, "results_buffers.json"), "w") as f:
        json.dump(results, f, default=float)

    def avg(f):
        return float(np.mean([f(r) for r in results]))

    print("== Is the buffer enough as often as promised? (all kinds of restaurant, unseen days) ==")
    print(f"{'method':14s}{'cover@80':>9s}{'cover@90':>9s}{'cover@95':>9s}{'shortage':>10s}{'leftover':>10s}{'pinball':>9s}")
    for m in METHODS:
        c = lambda s: np.mean([r["m"][m]["cov"][s] for r in results if s in r["m"][m]["cov"]]) * 100  # noqa: E731
        print(f"{m:14s}{c(0.8):8.1f}%{c(0.9):8.1f}%{c(0.95):8.1f}%{avg(lambda r: r['m'][m]['short']) * 100:9.2f}%{avg(lambda r: r['m'][m]['left']) * 100:9.1f}%"
              f"{avg(lambda r: r['m'][m]['pinball']) * 1000:9.2f}")
    print("\n== Coverage by kind of restaurant for today's method (targets 80/90/95) ==")
    for n in names:
        rs = [r for r in results if r["name"] == n]
        c = lambda s: np.mean([r["m"]["today"]["cov"][s] for r in rs if s in r["m"]["today"]["cov"]]) * 100  # noqa: E731
        print(f"{n:20s} 80->{c(0.8):5.1f}%   90->{c(0.9):5.1f}%   95->{c(0.95):5.1f}%   shortage {np.mean([r['m']['today']['short'] for r in rs]) * 100:5.2f}%   leftover {np.mean([r['m']['today']['left'] for r in rs]) * 100:5.1f}%")
    print("\n== Coverage by horizon (today's method, all restaurants), target about 86% on average ==")
    print("  ".join(f"day{h + 1}: {np.mean([r['m']['today']['cov_h'][h] for r in results]) * 100:4.1f}%" for h in range(HZ)))
    print("\n== Does a buffer measured for 'the first L days' still work for a window that starts LATER in the plan? (coverage, today's method) ==")
    for L in (2, 3, 4):
        print(f"windows of {L} days: " + "  ".join(f"start day {s}: {np.mean([r['window_cov'][f'L{L}_start{s}'] for r in results]) * 100:4.1f}%" for s in range(0, HZ - L + 1)))
    ac = np.mean([r["autocorr_by_3day_lag"] for r in results], axis=0)
    print("\n== How alike are the errors of planning days that are 3, 6, 9, 12 days apart? (correlation) ==")
    print("  ".join(f"{3 * (i + 1)} days apart: {a:+.2f}" for i, a in enumerate(ac)))


if __name__ == "__main__":
    main()
