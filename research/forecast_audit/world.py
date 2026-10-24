"""A flexible 'messy restaurant' generator for auditing the forecaster.

Deliberately NOT the app's own generator (data/generate.py): it uses different, smoother and noisier drivers so
that a good score cannot come from the model simply matching the way the test data was made.

make_world(...) returns a dict with
  q        wide daily sales the owner would see (days x dishes), including stock-out censoring and missing days
  q_true   what customers really wanted (before censoring and missing days)
  menu     DataFrame item_id, category, launch_date (what the app knows; discontinued dishes stay on it)
  cal      DataFrame type, label, start_date, end_date, name  (what the owner told the app)
  bom      dishes x ingredients quantity-per-serving
  ingr     DataFrame ingredient_id, shelf_life_days
"""
import numpy as np
import pandas as pd

CATS = ["main", "drink", "snack", "breakfast"]
CAT_DOW = {  # weekday shapes by category (Mon..Sun), mean about 1
    "main": [0.95, 0.95, 1.0, 1.0, 1.15, 1.1, 0.85],
    "drink": [0.9, 0.95, 1.0, 1.05, 1.15, 1.15, 0.8],
    "snack": [0.85, 0.9, 0.95, 1.0, 1.15, 1.3, 0.85],
    "breakfast": [1.2, 1.2, 1.15, 1.1, 1.0, 0.8, 0.55],
}


def make_world(
    seed: int = 0,
    days: int = 730,
    end: str = "2026-10-21",
    base: float = 200.0,
    n_dishes: int = 30,
    n_ingredients: int = 20,
    weekday_strength: float = 0.25,  # how different weekdays are
    closed_weekday: int | None = None,  # 0=Mon .. 6=Sun: the restaurant is closed that day every week
    random_closures: int = 3,  # per year
    trend_per_year: float = 0.05,
    seasonal_amp: float = 0.12,  # smooth yearly swing with NO calendar label
    day_shock_sd: float = 0.07,  # AR(1) 'weather / mood' shock, unknown to the model
    holiday_sd: float = 0.25,  # how different each holiday's effect is
    holiday_mean: float = 0.72,  # average holiday effect (0.3 = most holidays the shop is nearly closed)
    unknown_events_per_year: int = 4,  # busy days nobody told the app about
    outliers_per_year: int = 4,  # catering / big group days
    level_shift: bool = True,
    stockouts: bool = False,
    missing_days_pct: float = 0.0,
    new_dishes_per_year: int = 2,
    dropped_dishes_per_year: int = 2,
    labelled_periods: bool = False,  # does the owner also tell the app about busy/slow periods?
    dispersion: float = 10.0,  # negative-binomial k for dish counts (smaller = noisier)
) -> dict:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(end=end, periods=days)
    n = len(dates)
    t = np.arange(n)

    # ---- the day factor (applies to every dish) ----
    wk = np.array([0.88, 0.92, 0.97, 1.02, 1.22, 1.30, 0.78]) ** (weekday_strength / 0.25)
    wk = wk / wk.mean()
    wk = wk[rng.permutation(7)] if rng.random() < 0.3 else wk  # some restaurants peak on other days
    doy = dates.dayofyear.values
    seasonal = 1 + seasonal_amp * np.sin(2 * np.pi * (doy - rng.integers(0, 365)) / 365)
    trend = np.exp(trend_per_year * t / 365 + rng.normal(0, 0.03) * 0)
    shift = np.ones(n)
    if level_shift:
        s0 = rng.integers(n // 4, 3 * n // 4)
        shift[s0 : s0 + rng.integers(30, 70)] = rng.choice([0.88, 1.12])
    ar = np.zeros(n)
    for i in range(1, n):
        ar[i] = 0.5 * ar[i - 1] + rng.normal(0, day_shock_sd)
    shock = np.exp(ar)

    # public holidays: ~14 per year, some in pairs; each with its own effect, plus partial effect on neighbours
    hol_days, hol_rows, hol_fx = [], [], np.ones(n)
    n_hol = max(3, int(14 * n / 365))
    starts = np.sort(rng.choice(np.arange(5, n - 5), size=n_hol, replace=False))
    for k, s in enumerate(starts):
        length = 2 if rng.random() < 0.25 else 1
        eff = float(np.clip(rng.normal(holiday_mean, holiday_sd), 0.05, 1.6))
        for j in range(length):
            if s + j < n:
                hol_fx[s + j] *= eff
                hol_days.append(s + j)
        if s - 1 >= 0:
            hol_fx[s - 1] *= 1 + 0.3 * (eff - 1)
        if s + length < n:
            hol_fx[s + length] *= 1 + 0.5 * (eff - 1)
        hol_rows.append(("public_holiday", "public_holiday", dates[s], dates[min(s + length - 1, n - 1)], f"Holiday {k + 1}"))

    # events: some known to the app (in the calendar), some unknown
    ev_fx = np.ones(n)
    cal_rows = list(hol_rows)
    n_ev = int(unknown_events_per_year * n / 365)
    for k in range(n_ev):
        s = int(rng.integers(5, n - 5))
        ev_fx[s] *= rng.uniform(1.15, 1.45)
    n_known = int(3 * n / 365)
    for k in range(n_known):
        s = int(rng.integers(5, n - 5))
        ev_fx[s] *= rng.uniform(1.2, 1.5)
        cal_rows.append(("local_event", "local_event", dates[s], dates[s], f"Event {k + 1}"))
    out_fx = np.ones(n)
    for s in rng.choice(np.arange(5, n - 5), size=int(outliers_per_year * n / 365), replace=False):
        out_fx[s] = rng.uniform(1.8, 2.6)

    if labelled_periods:  # e.g. school terms: blocks of 60-120 days with distinct levels, told to the app
        pos, label_levels = 0, {}
        lab = ["term", "break", "festive"]
        while pos < n:
            length = int(rng.integers(60, 120))
            label = lab[int(rng.integers(0, 3))]
            label_levels.setdefault(label, rng.uniform(0.75, 1.25))
            seasonal[pos : pos + length] = label_levels[label] * (1 + 0.0 * seasonal[pos : pos + length])
            cal_rows.append(("period", label, dates[pos], dates[min(pos + length - 1, n - 1)], f"{label} {pos}"))
            pos += length

    day_factor = wk[dates.dayofweek.values] * seasonal * trend * shift * shock * hol_fx * ev_fx * out_fx  # the weekday swing is real

    closed = np.zeros(n, bool)
    if closed_weekday is not None:
        closed |= dates.dayofweek.values == closed_weekday
    for s in rng.choice(np.arange(5, n - 5), size=int(random_closures * n / 365), replace=False):
        closed[s] = True

    # ---- dishes ----
    shares = 1.0 / np.arange(1, n_dishes + 1) ** 0.8
    shares = shares[rng.permutation(n_dishes)]
    shares = shares / shares.sum()
    cats = [CATS[i] for i in rng.integers(0, len(CATS), n_dishes)]
    item_ids = np.arange(1, n_dishes + 1)
    launch = np.full(n_dishes, -1)
    dropped_at = np.full(n_dishes, n + 1)
    for i in rng.choice(n_dishes, size=min(n_dishes // 3, int(new_dishes_per_year * n / 365)), replace=False):
        launch[i] = rng.integers(60, n - 40)
    for i in rng.choice(n_dishes, size=min(n_dishes // 3, int(dropped_dishes_per_year * n / 365)), replace=False):
        if launch[i] < 0:
            dropped_at[i] = rng.integers(60, n - 40)
    drift = np.cumsum(rng.normal(0, 0.012, size=(n, n_dishes)), axis=0)  # slow change in popularity
    mu = np.zeros((n, n_dishes))
    for j in range(n_dishes):
        dow = np.array(CAT_DOW[cats[j]])[dates.dayofweek.values]
        dow = dow ** (weekday_strength / 0.25)
        s = shares[j] * np.exp(drift[:, j]) * dow
        if launch[j] >= 0:
            ramp = np.clip((t - launch[j]) / 21.0, 0, 1)
            s = s * ramp
        s = np.where(t >= dropped_at[j], 0.0, s)
        mu[:, j] = s
    mu = mu / np.maximum(mu.sum(axis=1, keepdims=True), 1e-9)  # mix sums to one each day
    lam = base * day_factor[:, None] * mu
    lam[closed] = 0
    qt = rng.negative_binomial(dispersion, dispersion / (dispersion + np.maximum(lam, 1e-9)))
    qt[lam <= 0] = 0
    q_true = pd.DataFrame(qt, index=dates, columns=item_ids)

    q = q_true.copy()
    if stockouts:  # the top dishes run out on ~7% of days, cutting that day's recorded sales to 55-85%
        top = np.argsort(-shares)[:5]
        for j in top:
            hit = rng.random(n) < 0.07
            q.iloc[:, j] = np.where(hit, (q.iloc[:, j] * rng.uniform(0.55, 0.85, n)).astype(int), q.iloc[:, j])
    if missing_days_pct > 0:
        gone = rng.random(n) < missing_days_pct
        q.loc[gone] = 0

    menu = pd.DataFrame(
        {
            "item_id": item_ids,
            "category": cats,
            "launch_date": [dates[launch[i]] if launch[i] >= 0 else pd.NaT for i in range(n_dishes)],
        }
    )

    # ---- recipes and ingredients ----
    ing_ids = np.arange(1, n_ingredients + 1)
    shelf = rng.choice([1, 2, 3, 4, 7, 14, 30, 90, 365], size=n_ingredients, p=[0.08, 0.1, 0.1, 0.08, 0.12, 0.12, 0.1, 0.15, 0.15])
    bom = pd.DataFrame(0.0, index=item_ids, columns=ing_ids)
    for j in item_ids:
        for g in rng.choice(ing_ids, size=int(rng.integers(2, 5)), replace=False):
            bom.loc[j, g] = float(rng.uniform(20, 250))
    ingr = pd.DataFrame({"ingredient_id": ing_ids, "shelf_life_days": shelf})

    cal = pd.DataFrame(cal_rows, columns=["type", "label", "start_date", "end_date", "name"])
    lam_total = pd.Series(lam.sum(axis=1), index=dates)  # the true expected total: an 'oracle' forecast
    return dict(q=q, q_true=q_true, menu=menu, cal=cal, bom=bom, ingr=ingr, closed=closed, dates=dates, lam_total=lam_total)
