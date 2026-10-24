from datetime import date, datetime

from pydantic import BaseModel, Field


class PlanCreate(BaseModel):
    horizon_days: int = Field(ge=1, le=7)
    today: date | None = None  # defaults to the app's "today" (see core/today.py)


class LinePatch(BaseModel):
    final_packs: int = Field(ge=0, le=10_000)


class RejectBody(BaseModel):
    reason: str = Field(min_length=1, max_length=300)


class LineOut(BaseModel):
    id: int
    ingredient_id: int
    name: str
    base_uom: str
    pack_uom: str
    pack_size_base: float
    need_base: float
    display_need: str
    buffer_pct: float
    buffer_base: float
    usable_stock_base: float
    display_usable_stock: str
    buy_schedule: list[dict]
    suggested_packs: int
    final_packs: int
    display_buy: str
    pack_price_rm: float
    line_total_rm: float
    leftover_base: float
    explanation: dict


class OrderOut(BaseModel):
    id: int
    run_id: int
    plan_today: date
    supplier_id: int
    supplier_name: str
    supplier_whatsapp: str
    min_order_rm: float
    status: str
    total_rm: float
    warnings: list[str]
    reject_reason: str | None
    created_at: datetime | None
    submitted_at: datetime | None
    approved_by: int | None
    approved_by_name: str | None
    approved_at: datetime | None
    sent_at: datetime | None
    received_at: datetime | None
    lines: list[LineOut]


class SendOut(BaseModel):
    order: OrderOut
    whatsapp_text: str
    whatsapp_url: str | None
    call_url: str | None = None


class ForecastDay(BaseModel):
    date: date
    weekday: str
    is_today: bool
    total: float
    drivers: dict


class ForecastDish(BaseModel):
    menu_item_id: int
    name: str
    category: str | None
    qty: list[float]  # one value per day, same order as `days`
    total: float


class ForecastOut(BaseModel):
    days: list[ForecastDay]
    dishes: list[ForecastDish]
    history: list[dict]  # last 28 days plus today (if it has sales) of real totals: {date, total}


class QualityOut(BaseModel):
    horizon_days: int
    wape_total: float
    baseline_naive_wape: float | None
    baseline_flat_wape: float | None
    computed_at: datetime


class PlanDetail(BaseModel):
    id: int
    created_at: datetime
    created_by: int | None
    created_by_name: str | None
    trigger: str
    today: date
    horizon_days: int
    risk_profile: str
    duration_ms: int
    calc_count: int
    manual_planning_hours: float
    grand_total_rm: float
    forecast: ForecastOut
    orders: list[OrderOut]
    discard: list[dict]
    covered: list[dict]
    exceptions: list[dict]
    forecast_quality: QualityOut | None
