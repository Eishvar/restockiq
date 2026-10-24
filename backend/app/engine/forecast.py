"""Demand forecast "calendar_topdown" and two simple baselines.

Port of data/reference_forecast.py (the maths is kept identical; tests compare the outputs):

  1. daily total T(d) = dishes sold that day
  2. weekday profile = median of T(d) / centred 7-day mean, per weekday (normal days only)
  3. learned effects: public holidays (incl. day before/after) and local events vs. surrounding days,
     shrunk toward 1 when there are few examples
  4. period level = median deseasonalised total per calendar state; blended over +-4 days at boundaries;
     recent strength = how busy the last 14 days were relative to their level (captures growth or decline)
  5. T^(d) = level(d) x strength x weekday(d) x holiday/event effects
  6. dishes = T^(d) x item share (70% last 28 days + 30% all history; new items: recent only)
             x category weekday adjustment, renormalised to T^(d)

With less than 8 weeks of history there is not enough to learn from, so a cold start is used instead:
the 4-week average level x weekday profile (flagged in every driver as cold_start).
"""
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd

from app.engine.calendar import calendar_features

COLD_START_DAYS = 56
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class Forecast:
    lines: pd.DataFrame  # date, item_id, qty, drivers
    days: pd.DataFrame  # date, total, drivers


def shrink(ratio: float, n: int, k: int = 3) -> float:
    """Pull a learned ratio toward 1 when it rests on few examples."""
    return (n * ratio + k * 1.0) / (n + k)


# ---------- input shaping ----------
def sales_to_wide(sales: pd.DataFrame) -> pd.DataFrame:
    """Long sales (date, item_id, qty; missing = 0) -> daily wide table, one column per dish."""
    q = sales.pivot_table(index="date", columns="item_id", values="qty", aggfunc="sum").fillna(0)
    q.index = pd.DatetimeIndex(q.index)
    return q.reindex(pd.date_range(q.index.min(), q.index.max()), fill_value=0)


def menu_frame(menu: pd.DataFrame) -> pd.DataFrame:
    """Menu (item_id, category, launch_date) indexed by item_id with a datetime launch_date."""
    m = menu.set_index("item_id").copy()
    m["launch_date"] = pd.to_datetime(m["launch_date"])
    return m


def calendar_for(cal: pd.DataFrame, q: pd.DataFrame, origin, horizon: int) -> pd.DataFrame:
    # 14 spare days beyond the horizon so the +-4 day boundary blend never runs off the end of the calendar
    last = max(q.index.max(), pd.Timestamp(origin) + timedelta(days=horizon - 1)) + timedelta(days=14)
    return calendar_features(cal, pd.date_range(q.index.min(), last))


# ---------- the forecaster ----------
def forecast_wide(q, menu, calf, origin, horizon) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Dishes for origin .. origin+horizon-1 using only history before origin.

    Returns (dishes: wide days x items, days: per-day driver table).
    """
    origin = pd.Timestamp(origin)
    h = q[q.index < origin]
    if h.empty:
        raise ValueError("No sales history before the forecast start")
    total = h.sum(axis=1)
    days = pd.date_range(origin, periods=horizon)
    cold = len(h) < COLD_START_DAYS

    if cold:
        dow = _weekday_profile(total, calf.loc[h.index], min_days=14)
        base = total.iloc[-28:].mean()
        tot = np.full(horizon, base) * dow.reindex(days.dayofweek).values
        info = pd.DataFrame(
            {
                "level": base,
                "strength": 1.0,
                "weekday_factor": dow.reindex(days.dayofweek).values,
                "holiday_effect": 1.0,
                "event_effect": 1.0,
            },
            index=days,
        )
    elif total.sum() <= 0:
        # nothing was ever sold: there is nothing to learn from, so forecast zero rather than guess
        info = pd.DataFrame(
            {"level": 0.0, "strength": 1.0, "weekday_factor": 1.0, "holiday_effect": 1.0, "event_effect": 1.0}, index=days
        )
        tot = np.zeros(horizon)
    else:
        cf = calf.loc[h.index]
        normal = ~cf.holiday & ~cf.event
        dow = _weekday_profile(total, cf)
        dow_at = dow.reindex(total.index.dayofweek).values
        # A weekday the shop is always closed on has a profile of 0: its days say nothing about how busy it is.
        dow_at = np.where(dow_at > 1e-6, dow_at, np.nan)
        des = total / dow_at
        # A day with no sales at all on an ordinary day is a closure (or missing data), not "demand was zero".
        # Holidays and events keep their zeros: closing on a holiday is exactly what the holiday effect should learn.
        des = des.where(~((total == 0) & normal))
        local = des.where(normal).rolling(15, center=True, min_periods=5).median()
        hol, ev = (des / local)[cf.holiday].dropna(), (des / local)[cf.event].dropna()
        hol_eff = shrink(hol.mean(), len(hol)) if len(hol) else 1.0
        ev_eff = shrink(ev.mean(), len(ev)) if len(ev) else 1.0
        clean = des.copy()
        clean[cf.holiday] /= hol_eff
        clean[cf.event] /= ev_eff
        level = clean.groupby(cf.state).median().dropna()  # a state seen only on closed days has no level
        fallback = clean.iloc[-14:].median()
        if not np.isfinite(fallback):  # the last two weeks were all closed: use the long-run level instead
            fallback = clean.median()
        if not np.isfinite(fallback):
            fallback = float(total[total > 0].mean())
        level_by_date = calf.state.map(lambda s: level.get(s, fallback))

        def smooth_level(d):  # people drift in/out around period boundaries, so blend +-4 days of levels
            window = level_by_date.reindex(pd.date_range(d - timedelta(days=4), d + timedelta(days=4))).dropna()
            return float(window.mean())

        recent = np.array([clean[d] / smooth_level(d) for d in clean.index[-14:]])
        recent = recent[np.isfinite(recent)]  # closed days carry no information about how busy the shop is
        strength = float(np.median(recent)) if len(recent) else 1.0
        tf = calf.loc[days]
        lvl = np.array([smooth_level(d) for d in days])
        wd = dow.reindex(days.dayofweek).values
        he = np.where(tf.holiday, hol_eff, 1.0)
        ee = np.where(tf.event, ev_eff, 1.0)
        tot = lvl * strength * wd * he * ee
        info = pd.DataFrame(
            {"level": lvl, "strength": strength, "weekday_factor": wd, "holiday_effect": he, "event_effect": ee},
            index=days,
        )

    info["total"] = tot
    info["state"] = calf.state.reindex(days).fillna("normal").values
    info["names"] = [calf["names"].get(d, ()) if "names" in calf else () for d in days]
    info["cold_start"] = cold
    return _split_dishes(h, menu, origin, days, tot, total), info


def _weekday_profile(total: pd.Series, cf: pd.DataFrame, min_days: int = 0) -> pd.Series:
    """Relative busyness of each weekday (mean 1), from normal days only."""
    if len(total) < min_days:
        return pd.Series(1.0, index=range(7))
    normal = ~cf.holiday & ~cf.event
    ratio = (total / total.rolling(7, center=True, min_periods=5).mean())[normal]
    dow = ratio.groupby(ratio.index.dayofweek).median().reindex(range(7)).fillna(1.0)
    return dow / dow.mean()


def _split_dishes(h, menu, origin, days, tot, total) -> pd.DataFrame:
    """Split each day's total into dishes by recent popularity and the category's weekday pattern."""
    s28 = h.iloc[-28:].sum() / max(h.iloc[-28:].sum().sum(), 1e-9)
    s_all = h.sum() / max(h.sum().sum(), 1e-9)
    launch = menu.launch_date.reindex(h.columns)
    new = launch.notna() & (launch > origin - timedelta(days=60))
    share = pd.Series(np.where(new, s28, 0.7 * s28 + 0.3 * s_all), index=h.columns)
    # A dish that sold nothing for four weeks although, given how busy the shop was, it would normally have sold at
    # least 5 has left the menu (or is out of season): it gets no share, instead of keeping 30% of its old one.
    # "Normally" = its usual share of all sales x the shop's total sales of those four weeks, so a quiet spell or a
    # closure (when the total is small) never makes a dish look discontinued. If it were still on the menu, the
    # chance of selling none while expecting 5 is under 1%.
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


# ---------- baselines (for the accuracy card) ----------
def naive_last_week(q: pd.DataFrame, origin, horizon: int) -> pd.DataFrame:
    """Same weekday last week."""
    origin = pd.Timestamp(origin)
    days = pd.date_range(origin, periods=horizon)
    src = [d - timedelta(days=7 * (i // 7 + 1)) for i, d in enumerate(days)]
    out = q.reindex(src).fillna(0)
    out.index = days
    return out


def flat_avg_4w(q: pd.DataFrame, origin, horizon: int) -> pd.DataFrame:
    """Average of the last 28 days, the same every day."""
    origin = pd.Timestamp(origin)
    h = q[q.index < origin].iloc[-28:]
    days = pd.date_range(origin, periods=horizon)
    return pd.DataFrame([h.mean().values] * horizon, index=days, columns=q.columns)


# ---------- public entry point ----------
def forecast_detail(sales_df, menu_df, calendar_df, start, horizon: int) -> Forecast:
    """Forecast dishes for `start .. start+horizon-1` from long-format inputs.

    sales_df: date, item_id, qty (only rows before `start` are used)
    menu_df: item_id, category, launch_date
    calendar_df: type, label, start_date, end_date, name
    """
    start = pd.Timestamp(start)
    sales = sales_df[pd.to_datetime(sales_df["date"]) < start].copy()
    sales["date"] = pd.to_datetime(sales["date"])
    q = sales_to_wide(sales)
    menu = menu_frame(menu_df)
    calf = calendar_for(calendar_df, q, start, horizon)
    wide, info = forecast_wide(q, menu, calf, start, horizon)

    day_drivers = {}
    for d, r in info.iterrows():
        day_drivers[d] = {
            "state": r.state,
            "weekday": WEEKDAYS[d.dayofweek],
            "weekday_factor": round(float(r.weekday_factor), 3),
            "level": round(float(r.level), 2),
            "strength": round(float(r.strength), 3),
            "holiday_effect": round(float(r.holiday_effect), 3),
            "event_effect": round(float(r.event_effect), 3),
            "names": list(r.names),
            "cold_start": bool(r.cold_start),
        }
    lines = wide.stack().rename("qty").reset_index()
    lines.columns = ["date", "item_id", "qty"]
    lines["drivers"] = lines["date"].map(day_drivers)
    days_df = pd.DataFrame(
        {"date": info.index, "total": info.total.values, "drivers": [day_drivers[d] for d in info.index]}
    )
    return Forecast(lines=lines, days=days_df)


def forecast(sales_df, menu_df, calendar_df, start, horizon: int) -> pd.DataFrame:
    """date, item_id, qty, drivers (see forecast_detail)."""
    return forecast_detail(sales_df, menu_df, calendar_df, start, horizon).lines
