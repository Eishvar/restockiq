import time

import pytest
from sqlalchemy import func, select

from app.modules.catalog.models import Ingredient
from app.modules.planning.data import load_safety
from app.modules.planning.models import ForecastQuality, SafetyProfile
from app.modules.planning.quality import recompute_safety
from app.modules.settings.models import Tenant


@pytest.fixture(scope="module")
def computed():
    """One shared database with the demo data and computed safety profiles (the backtest takes seconds)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db import init_db
    from app.seed.demo import ensure_demo_tenant
    from app.seed.load import load_demo_data

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    ensure_demo_tenant(db)
    load_demo_data(db, compute_safety=False)
    tenant = db.scalars(select(Tenant)).one()
    started = time.perf_counter()
    summary = recompute_safety(db, tenant)
    db.commit()
    yield db, tenant, summary, time.perf_counter() - started
    db.close()


def buffer_of(db, tenant, code, horizon=3):
    ing = db.scalars(select(Ingredient).where(Ingredient.code == code)).one()
    return db.get(SafetyProfile, (tenant.id, ing.id, horizon))


def test_recompute_safety_is_fast_enough(computed):
    _, _, summary, seconds = computed
    assert seconds < 60, f"recompute_safety took {seconds:.1f}s"
    assert summary["origins"] >= 60


def test_every_ingredient_has_a_buffer_for_every_horizon(computed):
    db, tenant, *_ = computed
    n_ing = db.scalar(select(func.count()).select_from(Ingredient))
    assert db.scalar(select(func.count()).select_from(SafetyProfile)) == n_ing * 7


def test_buffers_are_measured_percentages_close_to_the_reference(computed):
    db, tenant, *_ = computed
    for code, expected in {"CHICKEN_BREAST": 29, "RICE": 32, "EGG": 29}.items():
        row = buffer_of(db, tenant, code)
        assert row.method == "measured" and row.n_samples >= 12
        assert abs(row.buffer_pct - expected) <= 5, f"{code}: {row.buffer_pct}"
    assert buffer_of(db, tenant, "RICE").service_level == 0.95
    assert buffer_of(db, tenant, "EGG").service_level == 0.90
    assert buffer_of(db, tenant, "ICE").service_level == 0.80


def test_forecast_quality_stored_for_every_horizon(computed):
    db, tenant, *_ = computed
    rows = db.scalars(select(ForecastQuality).order_by(ForecastQuality.horizon_days)).all()
    assert [r.horizon_days for r in rows] == list(range(1, 8))
    seven = rows[-1]
    assert seven.model_name == "calendar_topdown"
    assert 0.10 < seven.wape_total < 0.17  # reference: 13.1%
    assert seven.wape_total < seven.baseline_naive_wape and seven.wape_total < seven.baseline_flat_wape


def test_load_safety_returns_fractions_for_the_engine(computed):
    db, tenant, *_ = computed
    df = load_safety(db, tenant.id)
    assert set(df.columns) >= {"ingredient_id", "horizon", "buffer", "service_level", "n_samples", "method"}
    assert df.buffer.between(0, 0.6).all()


def test_changing_the_risk_profile_changes_the_buffers(computed):
    db, tenant, *_ = computed
    before = buffer_of(db, tenant, "RICE").buffer_pct
    tenant.risk_profile = "lean"
    recompute_safety(db, tenant)
    lean = buffer_of(db, tenant, "RICE")
    assert lean.service_level == 0.90 and lean.buffer_pct < before
    tenant.risk_profile = "balanced"
    recompute_safety(db, tenant)
    assert buffer_of(db, tenant, "RICE").buffer_pct == pytest.approx(before)
    db.rollback()
