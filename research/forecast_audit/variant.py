"""A lab copy of app/engine/forecast.py with switches, to test each possible fix or improvement on its own.

With every switch off (the defaults) it must give EXACTLY the same numbers as the real engine (checked in check_variant.py).
"""
from datetime import timedelta

import numpy as np
import pandas as pd

from app.engine.forecast import COLD_START_DAYS, _weekday_profile, shrink


def holiday_masks(flags: pd.DataFrame, index) -> dict:
    """Separate masks: the holiday itself, the day before, the day after (each day counted once)."""
    f = flags.reindex(index).fillna(0)
    on = f.hol == 1
    before = (f.hol_before == 1) & ~on
    after = (f.hol_after == 1) & ~on & ~before
    return {"on": on.values, "before": before.values, "after": after.values}


def forecast_v(
    q, menu, calf, origin, horizon, *, flags=None,
    robust=False,  # closed days and zero-sales days no longer poison the level estimate
    strength_window=14, strength_stat="median", smooth_days=4, shrink_k=3,
    split_holiday=False,  # separate effects for the day before / the holiday / the day after
    drop_dead_dishes=False, share_window=28, share_recent=0.7,
    use_holiday=True, use_event=True,
    cold_shrink_k=None,  # None = the engine today; else shrink the weekday pattern of a short history toward 1: w = n/(n+k)
    cold_days=COLD_START_DAYS,
):
    origin = pd.Timestamp(origin)
    h = q[q.index < origin]
    total = h.sum(axis=1)
    days = pd.date_range(origin, periods=horizon)
    cold = len(h) < cold_days
    cf = calf.loc[h.index]

    if cold:
        dow = _weekday_profile(total, cf, min_days=14)
        if cold_shrink_k is not None:
            n_per_weekday = len(h) / 7.0
            wgt = 0.0 if cold_shrink_k == float("inf") else n_per_weekday / (n_per_weekday + cold_shrink_k)
            dow = 1 + (dow - 1) * wgt
        tot = np.full(horizon, total.iloc[-28:].mean()) * dow.reindex(days.dayofweek).values
        return _split(h, menu, origin, days, tot, total, drop_dead_dishes, share_window, share_recent), tot

    normal = ~cf.holiday & ~cf.event
    dow = _weekday_profile(total, cf)
    dow_at = dow.reindex(total.index.dayofweek).values
    if robust:
        dow_at = np.where(dow_at > 1e-6, dow_at, np.nan)  # a weekday the shop is always closed has no 'level'
    des = total / dow_at
    if robust:
        des = des.where(~((total == 0) & normal))  # a zero-sales day on an ordinary day is a closure, not demand
    local = des.where(normal).rolling(15, center=True, min_periods=5).median()
    ratio = des / local

    clean = des.copy()
    if split_holiday:
        m = holiday_masks(flags, h.index)
        eff = {}
        for k, mask in m.items():
            r = ratio[mask].dropna()
            eff[k] = shrink(r.mean(), len(r), shrink_k) if len(r) else 1.0
            clean[mask] /= eff[k]
        hol_eff_all = eff
    else:
        hol = ratio[cf.holiday].dropna()
        hol_eff = shrink(hol.mean(), len(hol), shrink_k) if (len(hol) and use_holiday) else 1.0
        clean[cf.holiday] /= hol_eff
    ev = ratio[cf.event].dropna()
    ev_eff = shrink(ev.mean(), len(ev), shrink_k) if (len(ev) and use_event) else 1.0
    clean[cf.event] /= ev_eff

    level = clean.groupby(cf.state).median()
    if robust:
        level = level.dropna()
    fallback = clean.iloc[-14:].median()
    if robust and not np.isfinite(fallback):
        fallback = clean.median()
    if robust and not np.isfinite(fallback):
        fallback = float(total[total > 0].mean())
    level_by_date = calf.state.map(lambda s: level.get(s, fallback))

    def smooth_level(d):
        window = level_by_date.reindex(pd.date_range(d - timedelta(days=smooth_days), d + timedelta(days=smooth_days))).dropna()
        return float(window.mean())

    vals = np.array([clean[d] / smooth_level(d) for d in clean.index[-strength_window:]])
    if robust:
        vals = vals[np.isfinite(vals)]
    if strength_stat == "median":
        strength = (float(np.median(vals)) if len(vals) else 1.0) if robust else float(np.median(vals))
    elif strength_stat == "mean":
        strength = float(np.nanmean(vals)) if len(vals) else 1.0
    else:  # trimmed mean: drop the top and bottom 20%
        v = np.sort(vals[np.isfinite(vals)])
        k = int(len(v) * 0.2)
        strength = float(v[k : len(v) - k].mean()) if len(v) > 2 * k else (float(np.median(v)) if len(v) else 1.0)
    if robust and not np.isfinite(strength):
        strength = 1.0

    tf = calf.loc[days]
    lvl = np.array([smooth_level(d) for d in days])
    wd = dow.reindex(days.dayofweek).values
    if split_holiday:
        mf = holiday_masks(flags, days)
        he = np.ones(horizon)
        for k, mask in mf.items():
            he = np.where(mask, hol_eff_all[k] if use_holiday else 1.0, he)
    else:
        he = np.where(tf.holiday, hol_eff, 1.0)
    ee = np.where(tf.event, ev_eff, 1.0)
    tot = lvl * strength * wd * he * ee
    return _split(h, menu, origin, days, tot, total, drop_dead_dishes, share_window, share_recent), tot


def _split(h, menu, origin, days, tot, total, drop_dead, share_window, share_recent):
    sw = h.iloc[-share_window:].sum() / max(h.iloc[-share_window:].sum().sum(), 1e-9)
    s_all = h.sum() / max(h.sum().sum(), 1e-9)
    launch = menu.launch_date.reindex(h.columns)
    new = launch.notna() & (launch > origin - timedelta(days=60))
    share = pd.Series(np.where(new, sw, share_recent * sw + (1 - share_recent) * s_all), index=h.columns)
    if drop_dead:
        # sold nothing for 4 weeks although its usual rate would have given at least 3 sales: gone, not unlucky
        expected_recent = s_all * float(total.iloc[-28:].sum())
        gone = (h.iloc[-28:].sum() == 0) & (expected_recent >= 5) & ~new
        share = share.where(~gone, 0.0)
    cats = menu.category.reindex(h.columns).fillna("other")
    cat_tot = h.T.groupby(cats).sum().T
    cat_dow = cat_tot.div(total.replace(0, np.nan), axis=0).groupby(cat_tot.index.dayofweek).mean()
    cat_dow = cat_dow.reindex(range(7)).fillna(cat_dow.mean())
    cat_dow = cat_dow / cat_dow.mean()
    rows = []
    for d, t in zip(days, tot):
        v = share.values * cat_dow.loc[d.dayofweek].reindex(cats.values).fillna(1.0).values
        s = v.sum()
        rows.append(pd.Series(v / s * t if s > 0 else v * 0.0, index=h.columns, name=d))
    return pd.DataFrame(rows)
