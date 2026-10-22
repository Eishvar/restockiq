"""Rolling-origin backtest: how wrong was the forecast in the past?

Each origin is a past date on which we pretend to be planning: forecast the next 7 days from the history
before it, then compare with what really sold. The relative ingredient-need errors feed the safety buffers
(engine/safety.py); the WAPE numbers feed the accuracy card.
"""
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd

from app.engine.forecast import COLD_START_DAYS, flat_avg_4w, forecast_wide, naive_last_week

HORIZONS = range(1, 8)
MODEL_NAME = "calendar_topdown"


@dataclass
class BacktestResult:
    errors: pd.DataFrame  # ingredient_id, horizon, origin, rel_err   (rel_err = actual / forecast - 1)
    quality: pd.DataFrame  # horizon_days, wape_total, wape_items, baseline_naive_wape, baseline_flat_wape
    n_origins: int


def rolling_origins(first_date, last_date, weeks: int = 34, step: int = 3, horizon: int = 7,
                    min_history_days: int = COLD_START_DAYS) -> list[pd.Timestamp]:
    """Origins every `step` days over the last `weeks` weeks, each with a full `horizon` of real sales
    after it and enough history before it.

    Two deliberate choices (checked against data/reference_forecast.py, which uses every 5 days from March):
    - The step does not divide 7. With a weekly step every origin falls on the same weekday, so a 3-day
      window would always start on, say, a Thursday and the buffers would only suit that weekday.
    - 34 weeks, not 26: a shorter window can miss the hardest stretch (the break -> semester switch)
      and under-size the buffers of eggs and similar items by several points.
    """
    newest = pd.Timestamp(last_date) - timedelta(days=horizon - 1)
    origins = [newest - timedelta(days=offset) for offset in range(0, weeks * 7, step)]
    return sorted(o for o in origins if (o - pd.Timestamp(first_date)).days >= min_history_days)


def backtest_all(q, menu, calf, bom, origins, horizons=HORIZONS) -> BacktestResult:
    """Run the forecaster at every origin once; return ingredient errors and forecast quality.

    q: wide daily sales (days x dishes); bom: dishes x ingredients quantity-per-serving matrix.
    """
    horizons = list(horizons)
    top = max(horizons)
    bom = bom.reindex(q.columns).fillna(0)
    ing_ids = bom.columns.to_numpy()
    err_rows = []
    # absolute-error sums per horizon: model, naive, flat (daily totals) and model (single dishes)
    abs_tot = {hz: np.zeros(3) for hz in horizons}
    abs_items = {hz: 0.0 for hz in horizons}
    actual_tot = {hz: 0.0 for hz in horizons}

    for o in origins:
        f, _ = forecast_wide(q, menu, calf, o, top)
        a = q.loc[f.index]
        naive, flat = naive_last_week(q, o, top), flat_avg_4w(q, o, top)
        for hz in horizons:
            fn = f.iloc[:hz].sum().to_numpy() @ bom.to_numpy()
            an = a.iloc[:hz].sum().to_numpy() @ bom.to_numpy()
            ok = fn > 0
            err_rows.append(
                pd.DataFrame(
                    {"ingredient_id": ing_ids[ok], "horizon": hz, "origin": o, "rel_err": an[ok] / fn[ok] - 1}
                )
            )
            at = a.iloc[:hz].sum(axis=1)
            actual_tot[hz] += at.sum()
            abs_tot[hz] += [
                (f.iloc[:hz].sum(axis=1) - at).abs().sum(),
                (naive.iloc[:hz].sum(axis=1) - at).abs().sum(),
                (flat.iloc[:hz].sum(axis=1) - at).abs().sum(),
            ]
            abs_items[hz] += (f.iloc[:hz] - a.iloc[:hz]).abs().to_numpy().sum()

    errors = (
        pd.concat(err_rows, ignore_index=True)
        if err_rows
        else pd.DataFrame(columns=["ingredient_id", "horizon", "origin", "rel_err"])
    )
    quality = pd.DataFrame(
        [
            {
                "horizon_days": hz,
                "wape_total": abs_tot[hz][0] / actual_tot[hz] if actual_tot[hz] else np.nan,
                "wape_items": abs_items[hz] / actual_tot[hz] if actual_tot[hz] else np.nan,
                "baseline_naive_wape": abs_tot[hz][1] / actual_tot[hz] if actual_tot[hz] else np.nan,
                "baseline_flat_wape": abs_tot[hz][2] / actual_tot[hz] if actual_tot[hz] else np.nan,
            }
            for hz in horizons
        ]
    )
    return BacktestResult(errors=errors, quality=quality, n_origins=len(origins))


def backtest(q, menu, calf, bom, origins, horizons=HORIZONS) -> pd.DataFrame:
    """Relative ingredient-need errors (actual / forecast - 1) for each origin and horizon."""
    return backtest_all(q, menu, calf, bom, origins, horizons).errors
