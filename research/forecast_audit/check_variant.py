import os, sys, warnings
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")]
warnings.simplefilter("ignore")
import numpy as np, pandas as pd
from app.engine.forecast import calendar_for, forecast_wide, menu_frame
from variant import forecast_v
from world import make_world

SCEN = {"typical": {}, "closed_monday": dict(closed_weekday=0), "menu_churn": dict(new_dishes_per_year=6, dropped_dishes_per_year=6),
        "closing_holidays": dict(holiday_mean=0.3, holiday_sd=0.3)}
worst_new = worst_old = 0.0
nan_new = nan_old = 0
for name, opts in SCEN.items():
    for seed in (0, 1):
        w = make_world(seed=seed, **opts)
        q = w["q"]
        menu = menu_frame(w["menu"]).reindex(q.columns)
        calf = calendar_for(w["cal"], q, q.index.max() + pd.Timedelta(days=1), 14)
        for back in (0, 9, 40, 100, 300):
            o = q.index.max() - pd.Timedelta(days=back + 6)
            real, _ = forecast_wide(q, menu, calf, o, 7)                                   # the engine as it is now
            lab_new, _ = forecast_v(q, menu, calf, o, 7, robust=True, drop_dead_dishes=True)  # lab copy with the fixes on
            lab_old, _ = forecast_v(q, menu, calf, o, 7)                                      # lab copy = the engine before the fixes
            worst_new = max(worst_new, float(np.nanmax(np.abs(real.values - lab_new.values))))
            nan_new += int((~np.isfinite(real.values)).any())
            nan_old += int((~np.isfinite(lab_old.values)).any())
print("real engine vs lab copy with fixes on: largest difference", worst_new, "| forecasts with NaN: real engine now", nan_new, "| before the fix", nan_old)
