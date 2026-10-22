from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SafetyProfile(Base):
    """Measured safety buffer per ingredient and horizon (filled by the backtest, read by plans)."""

    __tablename__ = "safety_profiles"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), primary_key=True)
    horizon_days: Mapped[int] = mapped_column(Integer, primary_key=True)  # 1-7
    service_level: Mapped[float] = mapped_column(Float)
    buffer_pct: Mapped[float] = mapped_column(Float)
    n_samples: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(20))  # measured | default
    computed_at: Mapped[datetime] = mapped_column(DateTime)


class ForecastQuality(Base):
    __tablename__ = "forecast_quality"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime)
    model_name: Mapped[str] = mapped_column(String(40))
    horizon_days: Mapped[int] = mapped_column(Integer)
    wape_total: Mapped[float] = mapped_column(Float)
    wape_items: Mapped[float | None] = mapped_column(Float, default=None)
    baseline_naive_wape: Mapped[float | None] = mapped_column(Float, default=None)
    baseline_flat_wape: Mapped[float | None] = mapped_column(Float, default=None)


class PlanRun(Base):
    __tablename__ = "plan_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    trigger: Mapped[str] = mapped_column(String(20), default="manual")  # manual | nightly
    today: Mapped[date] = mapped_column(Date)
    horizon_days: Mapped[int] = mapped_column(Integer)
    risk_profile: Mapped[str] = mapped_column(String(20))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    calc_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict | None] = mapped_column(JSON, default=None)


class ForecastLine(Base):
    __tablename__ = "forecast_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("plan_runs.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"))
    qty: Mapped[float] = mapped_column(Float)
    drivers: Mapped[dict | None] = mapped_column(JSON, default=None)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("plan_runs.id"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    # draft -> pending_approval -> approved -> sent -> received, or rejected
    status: Mapped[str] = mapped_column(String(20), default="draft")
    total_rm: Mapped[float] = mapped_column(Float, default=0)
    reject_reason: Mapped[str | None] = mapped_column(String(300), default=None)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)


class POLine(Base):
    __tablename__ = "po_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"))
    need_base: Mapped[float] = mapped_column(Float)
    buffer_pct: Mapped[float] = mapped_column(Float)
    buffer_base: Mapped[float] = mapped_column(Float)
    usable_stock_base: Mapped[float] = mapped_column(Float)
    buy_schedule: Mapped[list | None] = mapped_column(JSON, default=None)  # [{date, packs}]
    suggested_packs: Mapped[int] = mapped_column(Integer)
    final_packs: Mapped[int] = mapped_column(Integer)
    pack_price_rm: Mapped[float] = mapped_column(Float)
    line_total_rm: Mapped[float] = mapped_column(Float)
    leftover_base: Mapped[float] = mapped_column(Float, default=0)
    explanation: Mapped[dict | None] = mapped_column(JSON, default=None)
