"""Dashboard numbers: time saved, forecast accuracy, last plan, stock health, top spend."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.today import get_today
from app.modules.catalog.models import Ingredient, Supplier
from app.modules.dashboard.schemas import (
    Accuracy,
    DashboardOut,
    InventoryHealth,
    LastPlan,
    OrderStatus,
    SpendItem,
)
from app.modules.inventory.service import list_inventory
from app.modules.planning.models import ForecastQuality, PlanRun, POLine, PurchaseOrder
from app.modules.settings.models import Tenant, User

APPROVED_OR_LATER = ("approved", "sent", "received")


def dashboard(db: Session, user: User) -> DashboardOut:
    tid = user.tenant_id
    tenant = db.get(Tenant, tid)
    runs = list(db.scalars(select(PlanRun).where(PlanRun.tenant_id == tid).order_by(PlanRun.id)))
    orders = list(db.scalars(select(PurchaseOrder).where(PurchaseOrder.tenant_id == tid)))
    orders_by_run: dict[int, list[PurchaseOrder]] = {}
    for o in orders:
        orders_by_run.setdefault(o.run_id, []).append(o)

    # Time saved = completed plans x the manual baseline - the time people really spent (generated -> approved).
    completed, review_hours = 0, []
    for run in runs:
        approved = [o.approved_at for o in orders_by_run.get(run.id, []) if o.status in APPROVED_OR_LATER and o.approved_at]
        if approved:
            completed += 1
            review_hours.append(max((max(approved) - run.created_at).total_seconds(), 0) / 3600)
    hours_saved = completed * tenant.manual_planning_hours - sum(review_hours)

    last = runs[-1] if runs else None
    last_orders = orders_by_run.get(last.id, []) if last else []
    suppliers = {s.id: s.name for s in db.scalars(select(Supplier).where(Supplier.tenant_id == tid))}

    q = db.scalars(
        select(ForecastQuality).where(ForecastQuality.tenant_id == tid).order_by(ForecastQuality.horizon_days.desc(), ForecastQuality.id.desc())
    ).first()

    spend: dict[str, float] = {}
    if last_orders:
        names = {i.id: i.name for i in db.scalars(select(Ingredient).where(Ingredient.tenant_id == tid))}
        for line in db.scalars(select(POLine).where(POLine.po_id.in_([o.id for o in last_orders if o.status != "rejected"]))):
            spend[names[line.ingredient_id]] = spend.get(names[line.ingredient_id], 0) + line.line_total_rm

    today, _, items = list_inventory(db, user)
    expired = [i for i in items if i.status == "expired"]
    soon = [i for i in items if i.status == "expiring_soon"]
    return DashboardOut(
        today=today,
        plans_total=len(runs),
        plans_completed=completed,
        manual_hours_per_plan=tenant.manual_planning_hours,
        hours_saved=round(hours_saved, 2),
        avg_review_minutes=round(sum(review_hours) / len(review_hours) * 60, 1) if review_hours else None,
        last_plan=LastPlan(
            id=last.id, created_at=last.created_at, today=last.today, horizon_days=last.horizon_days,
            duration_ms=last.duration_ms, grand_total_rm=round(sum(o.total_rm for o in last_orders), 2),
        ) if last else None,
        accuracy=Accuracy(
            horizon_days=q.horizon_days, wape_total=q.wape_total, baseline_naive_wape=q.baseline_naive_wape,
            baseline_flat_wape=q.baseline_flat_wape,
        ) if q else None,
        orders=[OrderStatus(id=o.id, supplier_name=suppliers.get(o.supplier_id, "?"), status=o.status, total_rm=o.total_rm)
                for o in sorted(last_orders, key=lambda o: suppliers.get(o.supplier_id, ""))],
        inventory=InventoryHealth(
            ok=len(items) - len(expired) - len(soon), expiring_soon=len(soon), expired=len(expired),
            expired_items=[i.name for i in expired],
            expiring_items=[{"name": i.name, "days_left": i.days_left} for i in soon],
        ),
        top_spend=[SpendItem(name=n, total_rm=round(v, 2)) for n, v in sorted(spend.items(), key=lambda kv: -kv[1])[:5]],
    )
