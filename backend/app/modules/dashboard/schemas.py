from datetime import date, datetime

from pydantic import BaseModel


class LastPlan(BaseModel):
    id: int
    created_at: datetime
    today: date
    horizon_days: int
    duration_ms: int
    grand_total_rm: float


class Accuracy(BaseModel):
    horizon_days: int
    wape_total: float
    baseline_naive_wape: float | None
    baseline_flat_wape: float | None


class OrderStatus(BaseModel):
    id: int
    supplier_name: str
    status: str
    total_rm: float


class InventoryHealth(BaseModel):
    ok: int
    expiring_soon: int
    expired: int
    expired_items: list[str]
    expiring_items: list[dict]  # {name, days_left}


class SpendItem(BaseModel):
    name: str
    total_rm: float


class DashboardOut(BaseModel):
    today: date
    plans_total: int
    plans_completed: int  # plans with at least one approved order
    manual_hours_per_plan: float
    hours_saved: float
    avg_review_minutes: float | None
    last_plan: LastPlan | None
    accuracy: Accuracy | None
    orders: list[OrderStatus]
    inventory: InventoryHealth
    top_spend: list[SpendItem]
