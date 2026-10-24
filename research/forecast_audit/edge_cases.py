"""Does the forecaster behave sensibly when real-world data is awkward? (project venv; run with PYTHONPATH=backend)"""
import warnings

import numpy as np
import pandas as pd

from app.engine.forecast import forecast_detail
from world import make_world

warnings.simplefilter("ignore")


def to_long(q: pd.DataFrame) -> pd.DataFrame:
    s = q.stack()
    s = s[s > 0]
    return pd.DataFrame({"date": s.index.get_level_values(0), "item_id": s.index.get_level_values(1), "qty": s.values})


def run(name, w, q=None, start=None, horizon=8, menu=None, cal=None, trim=None):
    q = w["q"] if q is None else q
    if trim:
        q = q.iloc[-trim:]
    start = pd.Timestamp(start) if start is not None else q.index.max() + pd.Timedelta(days=1)
    try:
        fc = forecast_detail(to_long(q), (w["menu"] if menu is None else menu), (w["cal"] if cal is None else cal), start, horizon)
        tot = fc.days.set_index("date")["total"]
        bad = int((~np.isfinite(tot.values)).sum()) + int((tot.values < 0).sum())
        lines_bad = int((~np.isfinite(fc.lines.qty.values)).sum())
        recent = q.sum(axis=1).iloc[-28:]
        status = "OK " if bad == 0 and lines_bad == 0 else "BAD"
        print(f"{status} {name:46s} next-8-day totals: {np.round(tot.values[:8]).astype(int).tolist()}   (last-28-day mean {recent.mean():.0f})"
              + (f"   NaN/negative days: {bad}" if bad else ""))
        return fc
    except Exception as e:  # noqa: BLE001
        print(f"ERR {name:46s} {type(e).__name__}: {str(e)[:110]}")


w = make_world(seed=1, days=500, closed_weekday=None, random_closures=0, level_shift=False)
run("normal restaurant (control)", w)

wc = make_world(seed=1, days=500, closed_weekday=0, random_closures=0, level_shift=False)
run("closed EVERY Monday", wc)

wr = make_world(seed=1, days=500, closed_weekday=None, random_closures=12, level_shift=False)
run("12 random closed days a year", wr)

wm = make_world(seed=1, days=500, missing_days_pct=0.05, random_closures=0, level_shift=False)
run("5% of days missing from the export", wm)

for n in (5, 14, 30, 55, 56, 60, 90, 180):
    run(f"only {n} days of history", w, trim=n)

# shop shut for the last 14 days (renovation) and reopening
q2 = w["q"].copy()
q2.iloc[-14:] = 0
run("closed the last 14 days (renovation), reopening", w, q=q2)

# one dish only / two dishes
one = w["q"][[1]]
run("a menu with ONE dish", w, q=one, menu=w["menu"][w["menu"].item_id == 1])
two = w["q"][[1, 2]]
run("a menu with TWO dishes", w, q=two, menu=w["menu"][w["menu"].item_id.isin([1, 2])])

run("no calendar entries at all", w, cal=w["cal"].iloc[0:0])

run("forecast starting 6 days after the last sale", w, start=w["q"].index.max() + pd.Timedelta(days=6))

# an enormous one-off day inside the last 14 days
q3 = w["q"].copy()
q3.iloc[-5] = (q3.iloc[-5] * 8).astype(int)
f_out = run("a x8 catering day 5 days ago", w, q=q3)
f_ctl = run("(same, without the catering day)", w)

# a dish dropped from the menu 90 days ago but still 'active' in the app
q4 = w["q"].copy()
q4.iloc[-90:, 0] = 0
fc4 = forecast_detail(to_long(q4), w["menu"], w["cal"], q4.index.max() + pd.Timedelta(days=1), 8)
d1 = fc4.lines[fc4.lines.item_id == 1].qty.sum()
print(f"    dish 1 sold nothing for 90 days; forecast still gives it {d1:.1f} portions over the next 8 days"
      f" (it sold {w['q'].iloc[-180:-90, 0].mean():.1f}/day before it stopped)")

# a wide-open gap in the middle of the history (3 weeks missing)
q5 = w["q"].copy()
q5.iloc[-100:-79] = 0
run("a 3-week hole in the middle (POS was off)", w, q=q5)

# the calendar says a period/holiday but sales never exist for it yet (future label)
cal2 = pd.concat([w["cal"], pd.DataFrame([("period", "ramadan", w["q"].index.max() + pd.Timedelta(days=1), w["q"].index.max() + pd.Timedelta(days=30), "Ramadan")],
                                         columns=w["cal"].columns)], ignore_index=True)
run("a brand-new period label never seen before", w, cal=cal2)
