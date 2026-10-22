"""Measure how good the forecast is and how big the safety buffers must be (backtest -> tables).

Run at seed time, when the risk profile or calendar changes, and nightly. Plans only read the results.
"""
import time

import pandas as pd
from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from app.core.clock import now_kl
from app.engine.backtest import MODEL_NAME, backtest_all, rolling_origins
from app.engine.forecast import calendar_for, menu_frame, sales_to_wide
from app.engine.safety import safety_profiles
from app.modules.planning.data import load_frames
from app.modules.planning.models import ForecastQuality, SafetyProfile
from app.modules.settings.models import Tenant


def recompute_safety(db: Session, tenant: Tenant) -> dict:
    """Rebuild safety_profiles and forecast_quality for the tenant (flushes; the caller commits)."""
    started = time.perf_counter()
    f = load_frames(db, tenant.id)
    if f["sales"].empty:
        return {"origins": 0, "profiles": 0, "seconds": 0.0}

    q = sales_to_wide(f["sales"])
    menu = menu_frame(f["menu"])
    q = q.reindex(columns=menu.index.union(q.columns), fill_value=0)
    calf = calendar_for(f["calendar"], q, q.index.max() + pd.Timedelta(days=1), 14)
    bom = f["recipes"].pivot_table(index="item_id", columns="ingredient_id", values="qty_per_serving", aggfunc="sum")
    origins = rolling_origins(q.index.min(), q.index.max())
    result = backtest_all(q, menu.reindex(q.columns), calf, bom, origins)

    profiles = safety_profiles(result.errors, f["ingredients"], tenant.risk_profile)
    now = now_kl()
    db.execute(delete(SafetyProfile).where(SafetyProfile.tenant_id == tenant.id))
    db.execute(delete(ForecastQuality).where(ForecastQuality.tenant_id == tenant.id))
    if len(profiles):
        db.execute(
            insert(SafetyProfile),
            [
                dict(
                    tenant_id=tenant.id,
                    ingredient_id=int(r.ingredient_id),
                    horizon_days=int(r.horizon),
                    service_level=float(r.service_level),
                    buffer_pct=round(float(r.buffer) * 100, 2),
                    n_samples=int(r.n_samples),
                    method=r.method,
                    computed_at=now,
                )
                for r in profiles.itertuples(index=False)
            ],
        )
    quality = result.quality.dropna(subset=["wape_total"])
    if len(quality):
        db.execute(
            insert(ForecastQuality),
            [
                dict(
                    tenant_id=tenant.id,
                    computed_at=now,
                    model_name=MODEL_NAME,
                    horizon_days=int(r.horizon_days),
                    wape_total=float(r.wape_total),
                    wape_items=float(r.wape_items),
                    baseline_naive_wape=float(r.baseline_naive_wape),
                    baseline_flat_wape=float(r.baseline_flat_wape),
                )
                for r in quality.itertuples(index=False)
            ],
        )
    db.flush()
    return {
        "origins": result.n_origins,
        "profiles": len(profiles),
        "seconds": round(time.perf_counter() - started, 1),
    }
