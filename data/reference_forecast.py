"""Reference prototype of the RestockIQ forecaster, backtest and safety-buffer sizing.

Validated on this synthetic dataset; the app's engine/ (module M4) should port this logic into pure,
tested functions. Run: python reference_forecast.py   (prints accuracy + buffer tables)

Forecast ("calendar_topdown"):
  1. daily total T(d) = dishes sold that day
  2. weekday profile = median of T(d) / centred 7-day mean, per weekday (normal days only)
  3. learned effects: public holidays (incl. day before/after) and local events vs. surrounding days
  4. period level = median deseasonalised total per calendar "state" (combination of active period labels,
     e.g. "break+intake"); recent strength = how busy the last 14 days were relative to their period level
  5. T̂(d) = period level(d) × recent strength × weekday(d) × holiday/event effects
  6. dishes = T̂(d) × item share (70% last 28 days + 30% all history; new items: recent only)
             × category weekday adjustment (e.g. breakfast is a weekday thing)
Safety buffer: for each ingredient and horizon, the empirical quantile of past relative errors
  (actual need / forecast need − 1) at the target service level, shrunk toward the pooled value.
"""
from datetime import timedelta

import numpy as np
import pandas as pd

HERE = __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0] if ("\\" in __file__ or "/" in __file__) else "."


def load(data_dir: str = HERE):
    sales = pd.read_csv(f"{data_dir}/daily_sales.csv", parse_dates=["date"])
    menu = pd.read_csv(f"{data_dir}/menu_items.csv", parse_dates=["launch_date"]).set_index("item_id")
    cal = pd.read_csv(f"{data_dir}/calendar_events.csv", parse_dates=["start_date", "end_date"])
    rec = pd.read_csv(f"{data_dir}/recipes.csv")
    ing = pd.read_csv(f"{data_dir}/ingredients.csv").set_index("ingredient_id")
    q = sales.pivot_table(index="date", columns="item_id", values="qty", aggfunc="sum").fillna(0)
    q = q.reindex(pd.date_range(q.index.min(), q.index.max()), fill_value=0)
    bom = rec.pivot_table(index="item_id", columns="ingredient_id", values="qty_per_serving", aggfunc="sum")
    return q, menu, cal, bom.reindex(q.columns).fillna(0), ing


def calendar_features(cal: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    labels = {d: [] for d in dates}
    holiday = pd.Series(False, index=dates)
    event = pd.Series(False, index=dates)
    for _, e in cal.iterrows():
        if e.type == "period":
            for d in dates[(dates >= e.start_date) & (dates <= e.end_date)]:
                labels[d].append(e.label)
        elif e.type == "public_holiday":
            holiday[(dates >= e.start_date - timedelta(days=1)) & (dates <= e.end_date + timedelta(days=1))] = True
        elif e.type == "local_event":
            event[(dates >= e.start_date) & (dates <= e.end_date)] = True
    state = pd.Series(["+".join(sorted(set(v))) or "normal" for v in labels.values()], index=dates)
    return pd.DataFrame({"state": state, "holiday": holiday, "event": event})


def shrink(ratio: float, n: int, k: int = 3) -> float:
    return (n * ratio + k * 1.0) / (n + k)


def forecast(q, menu, calf, origin, horizon):
    """Item quantities for origin .. origin+horizon-1, using only history before origin."""
    h = q[q.index < origin]
    total = h.sum(axis=1)
    cf = calf.loc[h.index]
    normal = ~cf.holiday & ~cf.event
    ratio = (total / total.rolling(7, center=True, min_periods=5).mean())[normal]
    dow = ratio.groupby(ratio.index.dayofweek).median().reindex(range(7)).fillna(1.0)
    dow /= dow.mean()
    des = total / dow.reindex(total.index.dayofweek).values
    local = des.where(normal).rolling(15, center=True, min_periods=5).median()
    hol, ev = (des / local)[cf.holiday].dropna(), (des / local)[cf.event].dropna()
    hol_eff = shrink(hol.mean(), len(hol)) if len(hol) else 1.0
    ev_eff = shrink(ev.mean(), len(ev)) if len(ev) else 1.0
    clean = des.copy()
    clean[cf.holiday] /= hol_eff
    clean[cf.event] /= ev_eff
    level = clean.groupby(cf.state).median()
    fallback = clean.iloc[-14:].median()

    def smooth_level(d):  # people drift in/out around period boundaries, so blend ±4 days of levels
        window = calf.state.reindex(pd.date_range(d - timedelta(days=4), d + timedelta(days=4))).dropna()
        return float(np.mean([level.get(s, fallback) for s in window]))

    strength = np.median([clean[d] / smooth_level(d) for d in clean.index[-14:]])
    days = pd.date_range(origin, periods=horizon)
    tf = calf.loc[days]
    tot = np.array([smooth_level(d) for d in days]) * strength
    tot *= dow.reindex(days.dayofweek).values * np.where(tf.holiday, hol_eff, 1) * np.where(tf.event, ev_eff, 1)

    s28 = h.iloc[-28:].sum() / h.iloc[-28:].sum().sum()
    s_all = h.sum() / h.sum().sum()
    launch = menu.launch_date.reindex(h.columns)
    new = launch.notna() & (launch > origin - timedelta(days=60))
    share = pd.Series(np.where(new, s28, 0.7 * s28 + 0.3 * s_all), index=h.columns)
    cats = menu.category.reindex(h.columns)
    cat_tot = h.T.groupby(cats).sum().T
    cat_dow = cat_tot.div(total, axis=0).groupby(cat_tot.index.dayofweek).mean()
    cat_dow /= cat_dow.mean()
    rows = []
    for d, t in zip(days, tot):
        v = share.values * cat_dow.loc[d.dayofweek].reindex(cats.values).values
        rows.append(pd.Series(v / v.sum() * t, index=h.columns, name=d))
    return pd.DataFrame(rows)


def backtest(q, menu, calf, bom, origins, horizons=(1, 3, 7)):
    """Relative ingredient-need errors (actual/forecast − 1) for each origin and horizon."""
    errs = []
    for o in origins:
        f = forecast(q, menu, calf, o, max(horizons))
        a = q.loc[f.index]
        for hz in horizons:
            fn, an = f.iloc[:hz].sum() @ bom, a.iloc[:hz].sum() @ bom
            for g in bom.columns:
                if fn[g] > 0:
                    errs.append((g, hz, o, an[g] / fn[g] - 1))
    return pd.DataFrame(errs, columns=["ingredient_id", "horizon", "origin", "rel_err"])


def safety_buffers(errs, ing, service_level_for, min_n=12, default=0.15):
    """Buffer % per ingredient & horizon = empirical quantile of its own past errors at its service level.
    With fewer than min_n backtest samples (new restaurant) use a default; clipped to [0, 100%]."""
    out = []
    for (g, hz), grp in errs.groupby(["ingredient_id", "horizon"]):
        sl = service_level_for(ing.loc[g])
        n = len(grp)
        b = grp.rel_err.quantile(sl) if n >= min_n else default
        out.append((g, hz, sl, n, float(np.clip(b, 0, 1.0))))
    return pd.DataFrame(out, columns=["ingredient_id", "horizon", "service_level", "n", "buffer"])


def default_service_level(row) -> float:
    """Shortage costs more than leftovers; leftovers only cost money if they expire before use."""
    life = row.shelf_life_days
    return 0.95 if life >= 30 else 0.90 if life >= 7 else 0.80


if __name__ == "__main__":
    q, menu, cal, bom, ing = load()
    calf = calendar_features(cal, pd.date_range(q.index.min(), q.index.max() + timedelta(days=14)))
    origins = pd.date_range("2026-03-03", "2026-10-15", freq="5D")

    acc = []
    for o in origins:
        f = forecast(q, menu, calf, o, 7)
        a = q.loc[f.index]
        acc.append((abs(f.sum(axis=1) - a.sum(axis=1)).sum(), a.values.sum(), np.abs(f - a).values.sum()))
    acc = np.array(acc).sum(axis=0)
    print(f"7-day WAPE: daily totals {acc[0] / acc[1]:.1%}, single dishes {acc[2] / acc[1]:.1%}")

    errs = backtest(q, menu, calf, bom, origins)
    buf = safety_buffers(errs, ing, default_service_level)
    buf["life"] = buf.ingredient_id.map(ing.shelf_life_days)
    buf["class"] = pd.cut(buf.life, [0, 6, 29, 10_000], labels=["short <7d (80%)", "medium 7-29d (90%)", "long 30d+ (95%)"])
    print("\nmedian safety buffer by shelf-life class and horizon:")
    print((buf.groupby(["class", "horizon"], observed=True).buffer.median().unstack() * 100).round(0).to_string())
    pick = ["CHICKEN_BREAST", "CHICKEN_CHOP", "EGG", "RICE", "CHICKEN_LEG", "ICE", "FRESH_MILK", "MILO"]
    print("\nexamples (buffer % at horizon 3):")
    print((buf[(buf.horizon == 3) & buf.ingredient_id.isin(pick)].set_index("ingredient_id")[["service_level", "buffer"]]
           .assign(buffer=lambda x: (x.buffer * 100).round(0))).to_string())
