"""Planning workflow: generate a plan with the engine, then draft -> submit -> approve -> send -> receive.

Every consequential step calls log_action(); an invalid transition is a 409.
"""
import math
import time
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from fastapi import HTTPException
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.core.activity import log_action
from app.core.clock import now_kl
from app.core.today import get_today
from app.core.units import format_packs, format_qty
from app.engine.forecast import WEEKDAYS, forecast_detail
from app.engine.purchasing import plan_purchases
from app.engine.requirements import requirements
from app.modules.catalog.models import Ingredient, MenuItem, Supplier
from app.modules.inventory.service import add_stock
from app.modules.planning.data import load_frames, load_safety
from app.modules.planning.models import ForecastLine, ForecastQuality, PlanRun, POLine, PurchaseOrder
from app.modules.planning.schemas import (
    ForecastDay,
    ForecastDish,
    ForecastOut,
    LineOut,
    OrderOut,
    PlanDetail,
    QualityOut,
    SendOut,
)
from app.modules.planning.whatsapp import build_order_note, call_url, effective_schedule, whatsapp_number, whatsapp_url
from app.modules.setup.models import TenantSetup
from app.modules.sales.models import SalesDaily
from app.modules.settings.models import Tenant, User


def _py(o):
    """Make engine output JSON-safe: numpy scalars, NaN and dates."""
    if isinstance(o, dict):
        return {str(k): _py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_py(v) for v in o]
    if isinstance(o, np.generic):
        o = o.item()
    if isinstance(o, float) and math.isnan(o):
        return None
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    return o


def _sid(x) -> int | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else int(x)


# ---------- generate ----------
def generate_plan(db: Session, user: User, horizon_days: int, today: date | None = None) -> int:
    """Run the engine and save the plan run, forecast lines and one draft purchase order per supplier."""
    started = time.perf_counter()
    tenant = db.get(Tenant, user.tenant_id)
    today = today or get_today(db, tenant.id)
    f = load_frames(db, tenant.id)
    sales = f["sales"][f["sales"].item_id.isin(f["menu"].item_id)]
    if sales.empty:
        raise HTTPException(409, "There is no sales history yet, so nothing can be forecast")

    # today is forecast too (today's sales use stock before tomorrow); the shopping list starts tomorrow
    fc = forecast_detail(sales, f["menu"][["item_id", "category", "launch_date"]], f["calendar"], today, horizon_days + 1)
    reqs = requirements(fc.lines[["date", "item_id", "qty"]], f["recipes"], dict(zip(f["menu"].item_id, f["menu"].name)))
    result = plan_purchases(
        reqs.need, f["inventory"], f["ingredients"], f["suppliers"], load_safety(db, tenant.id),
        today, horizon_days, reqs.exceptions,
    )
    calc_count = len(fc.lines) + reqs.multiplications + result["calc_count"]

    exceptions = _py(result["exceptions"])
    run = PlanRun(
        tenant_id=tenant.id, created_at=now_kl(), created_by=user.id, trigger="manual", today=today,
        horizon_days=horizon_days, risk_profile=tenant.risk_profile, calc_count=calc_count,
    )
    db.add(run)
    db.flush()

    db.execute(
        insert(ForecastLine),
        [
            dict(tenant_id=tenant.id, run_id=run.id, date=r.date.date(), menu_item_id=int(r.item_id),
                 qty=float(r.qty), drivers=_py(r.drivers))
            for r in fc.lines.itertuples(index=False)
            if r.qty > 1e-6
        ],
    )

    orders = 0
    for group in result["suppliers"]:
        sid = _sid(group["supplier_id"])
        if sid is None:
            exceptions.append({"type": "no_supplier", "names": [l["name"] for l in group["lines"]]})
            continue
        po = PurchaseOrder(
            tenant_id=tenant.id, run_id=run.id, supplier_id=sid, status="draft",
            total_rm=group["subtotal_rm"], created_at=now_kl(),
        )
        db.add(po)
        db.flush()
        db.add_all(
            POLine(
                tenant_id=tenant.id, po_id=po.id, ingredient_id=int(l["ingredient_id"]), need_base=l["need_base"],
                buffer_pct=l["buffer_pct"], buffer_base=l["buffer_base"], usable_stock_base=l["usable_stock_base"],
                buy_schedule=_py(l["buy_schedule"]), suggested_packs=l["suggested_packs"],
                final_packs=l["suggested_packs"], pack_price_rm=l["pack_price_rm"], line_total_rm=l["line_total_rm"],
                leftover_base=l["leftover_base"], explanation=_py(l["explanation"]),
            )
            for l in group["lines"]
        )
        orders += 1

    run.duration_ms = int((time.perf_counter() - started) * 1000)
    run.summary = {
        "discard": _py(result["discard"]),
        "covered": _py(result["covered"]),
        "exceptions": exceptions,
        "days": [{"date": r.date.date().isoformat(), "total": round(float(r.total), 2), "drivers": _py(r.drivers)}
                 for r in fc.days.itertuples(index=False)],
    }
    log_action(
        db, user, "plan_generated", "plan_run", run.id,
        {"horizon_days": horizon_days, "today": today.isoformat(), "orders": orders,
         "grand_total_rm": result["grand_total_rm"], "duration_ms": run.duration_ms, "calc_count": calc_count},
    )
    db.commit()
    return run.id


# ---------- read ----------
def context(db: Session, user: User) -> dict:
    last = db.scalars(select(PlanRun).where(PlanRun.tenant_id == user.tenant_id).order_by(PlanRun.id.desc())).first()
    return {"today": get_today(db, user.tenant_id).isoformat(), "last_plan_id": last.id if last else None}



def _sales_changed_at(db: Session, tenant_id: int) -> datetime | None:
    row = db.get(TenantSetup, tenant_id)
    return row.sales_changed_at if row else None


def _older(made_at: datetime | None, changed: datetime | None) -> bool:
    """True when sales data changed after something was made, so it used the older numbers."""
    return bool(made_at and changed and made_at < changed)


def _orders_out(db: Session, tenant_id: int, orders: list[PurchaseOrder]) -> list[OrderOut]:
    if not orders:
        return []
    ids = [o.id for o in orders]
    suppliers = {s.id: s for s in db.scalars(select(Supplier).where(Supplier.tenant_id == tenant_id))}
    ingredients = {i.id: i for i in db.scalars(select(Ingredient).where(Ingredient.tenant_id == tenant_id))}
    users = {u.id: u.name for u in db.scalars(select(User).where(User.tenant_id == tenant_id))}
    runs = {r.id: r for r in db.scalars(select(PlanRun).where(PlanRun.id.in_({o.run_id for o in orders})))}
    changed = _sales_changed_at(db, tenant_id)
    lines: dict[int, list[POLine]] = {}
    for l in db.scalars(select(POLine).where(POLine.po_id.in_(ids)).order_by(POLine.id)):
        lines.setdefault(l.po_id, []).append(l)

    out = []
    for o in orders:
        sup = suppliers[o.supplier_id]
        line_out = []
        for l in sorted(lines.get(o.id, []), key=lambda x: ingredients[x.ingredient_id].name):
            ing = ingredients[l.ingredient_id]
            line_out.append(
                LineOut(
                    id=l.id, ingredient_id=l.ingredient_id, name=ing.name, base_uom=ing.base_uom, pack_uom=ing.pack_uom,
                    pack_size_base=ing.pack_size_base, need_base=l.need_base, display_need=format_qty(l.need_base, ing.base_uom),
                    buffer_pct=l.buffer_pct, buffer_base=l.buffer_base, usable_stock_base=l.usable_stock_base,
                    display_usable_stock=format_qty(l.usable_stock_base, ing.base_uom), buy_schedule=l.buy_schedule or [],
                    suggested_packs=l.suggested_packs, final_packs=l.final_packs,
                    display_buy=format_packs(l.final_packs, ing.pack_uom), pack_price_rm=l.pack_price_rm,
                    line_total_rm=l.line_total_rm, leftover_base=l.leftover_base, explanation=l.explanation or {},
                )
            )
        warnings = []
        if 0 < o.total_rm < sup.min_order_rm:
            warnings.append(f"Below the supplier's minimum order of RM {sup.min_order_rm:,.2f}")
        out.append(
            OrderOut(
                id=o.id, run_id=o.run_id, plan_today=runs[o.run_id].today, supplier_id=o.supplier_id,
                supplier_name=sup.name, supplier_whatsapp=sup.whatsapp, min_order_rm=sup.min_order_rm,
                status=o.status, total_rm=o.total_rm, warnings=warnings, reject_reason=o.reject_reason,
                created_at=o.created_at, submitted_at=o.submitted_at, approved_by=o.approved_by,
                approved_by_name=users.get(o.approved_by), approved_at=o.approved_at, sent_at=o.sent_at,
                received_at=o.received_at, lines=line_out, note_text=o.note_text,
                plan_is_stale=o.status in ("draft", "pending_approval") and _older(runs[o.run_id].created_at, changed),
            )
        )
    return out


def list_orders(db: Session, user: User, status: str | None = None) -> list[OrderOut]:
    stmt = select(PurchaseOrder).where(PurchaseOrder.tenant_id == user.tenant_id).order_by(PurchaseOrder.id.desc())
    if status:
        stmt = stmt.where(PurchaseOrder.status == status)
    return _orders_out(db, user.tenant_id, list(db.scalars(stmt)))


def get_order(db: Session, user: User, order_id: int) -> OrderOut:
    return _orders_out(db, user.tenant_id, [_order(db, user, order_id)])[0]


def get_plan_detail(db: Session, user: User, run_id: int) -> PlanDetail:
    run = db.get(PlanRun, run_id)
    if run is None or run.tenant_id != user.tenant_id:
        raise HTTPException(404, "Plan not found")
    tenant = db.get(Tenant, user.tenant_id)
    summary = run.summary or {}
    orders = _orders_out(
        db, user.tenant_id,
        list(db.scalars(select(PurchaseOrder).where(PurchaseOrder.run_id == run.id).order_by(PurchaseOrder.id))),
    )

    days = [
        ForecastDay(date=d["date"], weekday=WEEKDAYS[date.fromisoformat(d["date"]).weekday()],
                    is_today=d["date"] == run.today.isoformat(), total=d["total"], drivers=d["drivers"])
        for d in summary.get("days", [])
    ]
    index = {d.date.isoformat(): i for i, d in enumerate(days)}
    names = {m.id: (m.name, m.category) for m in db.scalars(select(MenuItem).where(MenuItem.tenant_id == user.tenant_id))}
    per_dish: dict[int, list[float]] = {}
    for fl in db.scalars(select(ForecastLine).where(ForecastLine.run_id == run.id)):
        per_dish.setdefault(fl.menu_item_id, [0.0] * len(days))[index[fl.date.isoformat()]] = round(fl.qty, 1)
    dishes = sorted(
        (ForecastDish(menu_item_id=i, name=names[i][0], category=names[i][1], qty=q, total=round(sum(q), 1))
         for i, q in per_dish.items() if sum(q) >= 0.5),
        key=lambda d: -d.total,
    )
    start = run.today - timedelta(days=28)
    actual = dict(
        db.execute(
            select(SalesDaily.date, func.sum(SalesDaily.qty))
            .where(SalesDaily.tenant_id == user.tenant_id, SalesDaily.date >= start, SalesDaily.date <= run.today)
            .group_by(SalesDaily.date)
        ).all()
    )
    history = [{"date": (start + timedelta(days=i)).isoformat(), "total": int(actual.get(start + timedelta(days=i), 0))}
               for i in range(29)]  # 28 days before today, plus today when it has sales

    q = db.scalars(
        select(ForecastQuality)
        .where(ForecastQuality.tenant_id == user.tenant_id, ForecastQuality.horizon_days == min(run.horizon_days, 7))
        .order_by(ForecastQuality.id.desc())
    ).first()
    creator = db.get(User, run.created_by) if run.created_by else None
    return PlanDetail(
        id=run.id, created_at=run.created_at, created_by=run.created_by, created_by_name=creator.name if creator else None,
        trigger=run.trigger, today=run.today, horizon_days=run.horizon_days, risk_profile=run.risk_profile,
        duration_ms=run.duration_ms, calc_count=run.calc_count, manual_planning_hours=tenant.manual_planning_hours,
        grand_total_rm=round(sum(o.total_rm for o in orders), 2),
        forecast=ForecastOut(days=days, dishes=dishes, history=history), orders=orders,
        data_changed_since=_older(run.created_at, _sales_changed_at(db, user.tenant_id)),
        discard=summary.get("discard", []), covered=summary.get("covered", []), exceptions=summary.get("exceptions", []),
        forecast_quality=QualityOut(
            horizon_days=q.horizon_days, wape_total=q.wape_total, baseline_naive_wape=q.baseline_naive_wape,
            baseline_flat_wape=q.baseline_flat_wape, computed_at=q.computed_at,
        ) if q else None,
    )


# ---------- state machine ----------
def _order(db: Session, user: User, order_id: int) -> PurchaseOrder:
    po = db.get(PurchaseOrder, order_id)
    if po is None or po.tenant_id != user.tenant_id:
        raise HTTPException(404, "Order not found")
    return po


def _require_status(po: PurchaseOrder, *allowed: str) -> None:
    if po.status not in allowed:
        raise HTTPException(409, f"This order is '{po.status}'. It must be '{' or '.join(allowed)}' for this step.")


def _lines(db: Session, po: PurchaseOrder) -> list[POLine]:
    return list(db.scalars(select(POLine).where(POLine.po_id == po.id).order_by(POLine.id)))


def edit_line(db: Session, user: User, order_id: int, line_id: int, final_packs: int) -> OrderOut:
    po = _order(db, user, order_id)
    _require_status(po, "draft")
    line = db.get(POLine, line_id)
    if line is None or line.po_id != po.id:
        raise HTTPException(404, "Line not found")
    if final_packs != line.final_packs:
        ing = db.get(Ingredient, line.ingredient_id)
        before = {"final_packs": line.final_packs, "line_total_rm": line.line_total_rm}
        # extra packs end up on the shelf; fewer packs leave less over (never below zero)
        line.leftover_base = round(max(0.0, line.leftover_base + (final_packs - line.final_packs) * ing.pack_size_base), 3)
        line.final_packs = final_packs
        line.line_total_rm = round(final_packs * line.pack_price_rm, 2)
        db.flush()
        po.total_rm = round(sum(l.line_total_rm for l in _lines(db, po)), 2)
        log_action(
            db, user, "po_line_edited", "purchase_order", po.id,
            {"line_id": line.id, "item": ing.name, "before": before,
             "after": {"final_packs": line.final_packs, "line_total_rm": line.line_total_rm}},
        )
    db.commit()
    return get_order(db, user, order_id)


def submit(db: Session, user: User, order_id: int) -> OrderOut:
    po = _order(db, user, order_id)
    _require_status(po, "draft")
    if po.total_rm <= 0:
        raise HTTPException(409, "Nothing to order: every line is set to 0 packs")
    po.status, po.submitted_at = "pending_approval", now_kl()
    log_action(db, user, "po_submitted", "purchase_order", po.id, {"total_rm": po.total_rm})
    db.commit()
    return get_order(db, user, order_id)


def approve(db: Session, user: User, order_id: int) -> OrderOut:
    po = _order(db, user, order_id)
    _require_status(po, "pending_approval")
    po.status, po.approved_by, po.approved_at = "approved", user.id, now_kl()
    po.note_text = _note_for_order(db, user, po)  # written now, so what was approved is exactly what gets sent
    log_action(db, user, "po_approved", "purchase_order", po.id, {"total_rm": po.total_rm, "note_prepared": True})
    db.commit()
    return get_order(db, user, order_id)


def reject(db: Session, user: User, order_id: int, reason: str) -> OrderOut:
    po = _order(db, user, order_id)
    _require_status(po, "pending_approval")
    po.status, po.reject_reason = "rejected", reason.strip()
    log_action(db, user, "po_rejected", "purchase_order", po.id, {"reason": po.reject_reason, "total_rm": po.total_rm})
    db.commit()
    return get_order(db, user, order_id)


def _note_for_order(db: Session, user: User, po: PurchaseOrder) -> str:
    """The order note: reference, dates, every line with its price, and the total."""
    sup = db.get(Supplier, po.supplier_id)
    tenant = db.get(Tenant, user.tenant_id)
    items = []
    for l in _lines(db, po):
        if l.final_packs > 0:
            ing = db.get(Ingredient, l.ingredient_id)
            items.append({"name": ing.name, "pack_uom": ing.pack_uom, "pack_price_rm": l.pack_price_rm,
                          "schedule": effective_schedule(l.buy_schedule or [], l.suggested_packs, l.final_packs)})
    return build_order_note(po.id, sup.name, tenant.name, (po.approved_at or now_kl()).date(), items, po.total_rm)


def _message_for_order(db: Session, user: User, po: PurchaseOrder) -> tuple[str, str | None, str | None]:
    sup = db.get(Supplier, po.supplier_id)
    text = po.note_text or _note_for_order(db, user, po)  # an order approved before notes were saved gets one built now
    number = whatsapp_number(sup.whatsapp)
    return text, whatsapp_url(number, text), call_url(number)


def prepare_order_message(db: Session, user: User, order_id: int) -> SendOut:
    """Create the supplier message without changing order status."""
    po = _order(db, user, order_id)
    _require_status(po, "draft", "pending_approval", "approved", "sent")
    text, url, phone_url = _message_for_order(db, user, po)
    return SendOut(order=get_order(db, user, order_id), whatsapp_text=text, whatsapp_url=url, call_url=phone_url)


def send(db: Session, user: User, order_id: int) -> SendOut:
    """Approved -> sent. Returns the WhatsApp text and a wa.me link. Asking again for a sent order just
    returns the same message (no new log entry), so the owner can reopen the chat."""
    po = _order(db, user, order_id)
    _require_status(po, "approved", "sent")
    sup = db.get(Supplier, po.supplier_id)
    text, url, phone_url = _message_for_order(db, user, po)
    if po.status == "approved":
        po.status, po.sent_at = "sent", now_kl()
        log_action(db, user, "po_sent", "purchase_order", po.id,
                   {"supplier": sup.name, "channel": "whatsapp", "has_number": url is not None, "total_rm": po.total_rm})
    db.commit()
    return SendOut(order=get_order(db, user, order_id), whatsapp_text=text, whatsapp_url=url, call_url=phone_url)


def receive(db: Session, user: User, order_id: int) -> OrderOut:
    """Approved or sent -> received: add the packs to stock as a new batch dated today."""
    po = _order(db, user, order_id)
    _require_status(po, "approved", "sent")
    today = get_today(db, user.tenant_id)
    added = []
    for l in _lines(db, po):
        if l.final_packs <= 0:
            continue
        ing = db.get(Ingredient, l.ingredient_id)
        qty = l.final_packs * ing.pack_size_base
        # Each delivery is its own batch dated today, so older stock keeps its own (earlier) expiry date.
        add_stock(db, user, ing, qty, today, "received", f"Order #{po.id}", pack_price_rm=l.pack_price_rm)
        added.append({"item": ing.name, "packs": l.final_packs, "qty_base": qty})
    po.status, po.received_at = "received", now_kl()
    log_action(db, user, "po_received", "purchase_order", po.id,
               {"lines": added, "total_rm": po.total_rm})
    db.commit()
    return get_order(db, user, order_id)
