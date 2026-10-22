"""Safety buffers measured from the restaurant's own past forecast errors.

For each ingredient and horizon the buffer is the empirical quantile of its backtest errors at a target
service level (the share of past cases in which the buffer was enough). The service level depends on shelf
life and the owner's risk profile: shortages cost more than leftovers, and leftovers of long-life items are
not wasted. With too few samples (new restaurant / new ingredient) a default is used and flagged.
"""
import numpy as np
import pandas as pd

HORIZONS = range(1, 8)
MIN_SAMPLES = 12
DEFAULT_BUFFER = 0.15
MAX_BUFFER = 0.60

# risk profile -> service level for (short < 7 days, medium 7-29 days, long >= 30 days)
SERVICE_LEVELS = {
    "lean": (0.70, 0.80, 0.90),
    "balanced": (0.80, 0.90, 0.95),
    "never_run_out": (0.90, 0.95, 0.98),
}


def service_level(shelf_life_days: float, risk_profile: str = "balanced") -> float:
    short, medium, long_ = SERVICE_LEVELS[risk_profile]
    return long_ if shelf_life_days >= 30 else medium if shelf_life_days >= 7 else short


def safety_profiles(
    errors: pd.DataFrame,
    ingredients: pd.DataFrame,
    risk_profile: str = "balanced",
    min_samples: int = MIN_SAMPLES,
    default: float = DEFAULT_BUFFER,
    max_buffer: float = MAX_BUFFER,
    horizons=HORIZONS,
) -> pd.DataFrame:
    """One row per ingredient x horizon:

    ingredient_id, horizon, service_level, buffer (a fraction: 0.29 = +29%), n_samples, method

    `ingredients` needs ingredient_id and shelf_life_days. Ingredients with no recipe use appear too
    (n_samples 0, default buffer) so every ingredient has a value.
    """
    grouped = {k: g.rel_err.to_numpy() for k, g in errors.groupby(["ingredient_id", "horizon"])}
    rows = []
    for ing in ingredients.itertuples(index=False):
        sl = service_level(ing.shelf_life_days, risk_profile)
        for hz in horizons:
            errs = grouped.get((ing.ingredient_id, hz), np.array([]))
            n = len(errs)
            if n >= min_samples:
                buffer, method = float(np.quantile(errs, sl)), "measured"
            else:
                buffer, method = default, "default"
            rows.append((ing.ingredient_id, hz, sl, float(np.clip(buffer, 0.0, max_buffer)), n, method))
    return pd.DataFrame(
        rows, columns=["ingredient_id", "horizon", "service_level", "buffer", "n_samples", "method"]
    )
