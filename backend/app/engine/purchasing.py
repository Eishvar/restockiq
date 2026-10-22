"""Shelf-life-aware purchasing: what to buy, when, from whom, and why.

Per ingredient, from today (today's expected use is included because today's sales consume stock before
tomorrow) to the end of the horizon:

  1. Expired stock (last purchased + shelf life <= today) is excluded and listed for discarding.
  2. Day by day: drop expired lots, then use the oldest stock first.
  3. When a day from tomorrow on would run short, buy on that day to cover that day .. min(day + shelf life
     - 1, end of horizon):  target = need in window x (1 + safety buffer for that window length);
     packs = ceil((target - usable stock) / pack size). The new lot expires shelf-life days later.
     Leftovers (buffer + pack rounding) carry forward while fresh, so later trips buy less.
  4. Each line carries a structured explanation; supplier subtotals, warnings and exceptions are added.

Pure function: no database, no clock, no LLM.
"""
import math
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from app.engine.safety import DEFAULT_BUFFER

EPS = 1e-9


@dataclass
class Lot:
    qty: float
    expiry: date  # usable on days strictly before this date


def _d(x) -> date:
    return pd.Timestamp(x).date()


def _consume(lots: list[Lot], need: float) -> float:
    """Use the oldest stock first; returns the shortage that could not be met."""
    for lot in sorted(lots, key=lambda l: l.expiry):
        take = min(lot.qty, need)
        lot.qty -= take
        need -= take
        if need <= EPS:
            return 0.0
    return need


def _usable_in_window(lots: list[Lot], needs: list[tuple[date, float]]) -> float:
    """Stock that will really be usable over the window: everything except what expires unused."""
    sim = [Lot(l.qty, l.expiry) for l in lots]
    total = sum(l.qty for l in sim)
    wasted = 0.0
    for i, (day, need) in enumerate(needs):
        if i > 0:
            wasted += sum(l.qty for l in sim if l.expiry <= day)
            sim = [l for l in sim if l.expiry > day]
        _consume(sim, need)
    return total - wasted


def plan_purchases(
    need_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    ingredients_df: pd.DataFrame,
    suppliers_df: pd.DataFrame,
    safety_df: pd.DataFrame,
    today,
    horizon: int,
    exceptions: list[dict] | None = None,
) -> dict:
    """Build the purchase plan.

    need_df:        date, ingredient_id, need_base   (forecast use, from today to today + horizon)
    inventory_df:   ingredient_id, qty_base, last_purchased_on
    ingredients_df: ingredient_id, name, supplier_id, base_uom, pack_uom, pack_size_base, pack_price_rm,
                    shelf_life_days
    suppliers_df:   supplier_id, name, min_order_rm
    safety_df:      ingredient_id, horizon, buffer (fraction), service_level, n_samples, method
    Returns {suppliers, discard, covered, grand_total_rm, exceptions, calc_count}.
    """
    today = _d(today)
    days = [today + timedelta(days=i) for i in range(horizon + 1)]
    end = days[-1]

    need_by = {}
    for r in need_df.itertuples(index=False):
        need_by.setdefault(r.ingredient_id, {})[_d(r.date)] = float(r.need_base)
    stock_by = {
        r.ingredient_id: (float(r.qty_base), None if pd.isna(r.last_purchased_on) else _d(r.last_purchased_on))
        for r in inventory_df.itertuples(index=False)
    }
    safety_by = {(r.ingredient_id, int(r.horizon)): r for r in safety_df.itertuples(index=False)}
    sup_by = {r.supplier_id: r for r in suppliers_df.itertuples(index=False)}

    calc_count = len(need_df)
    discard, covered, lines_by_supplier, out_exceptions = [], [], {}, list(exceptions or [])

    for ing in ingredients_df.itertuples(index=False):
        g, shelf = ing.ingredient_id, int(ing.shelf_life_days)
        qty, bought_on = stock_by.get(g, (0.0, None))
        need = need_by.get(g, {})
        if not any(v > 0 for v in need.values()):  # no dish uses it, so nothing will ever be planned for it
            out_exceptions.append({"type": "no_forecast_use", "ingredient_id": g, "name": ing.name})

        # 1. expired stock is excluded and listed for discarding
        lots, expiry = [], None
        if qty > 0:
            expiry = (bought_on + timedelta(days=shelf)) if bought_on else today + timedelta(days=shelf)
            if expiry <= today:
                discard.append(
                    {"ingredient_id": g, "name": ing.name, "qty_base": round(qty, 3), "expired_on": expiry.isoformat(),
                     "days_ago": (today - expiry).days}
                )
            else:
                lots.append(Lot(qty, expiry))
        stock_info = {
            "qty_base": round(qty, 3),
            "expires_on": expiry.isoformat() if expiry else None,
            "expired": bool(expiry and expiry <= today),
            "purchase_date_unknown": bool(qty > 0 and bought_on is None),
        }

        # 2./3. simulate day by day, buying when a day from tomorrow on would run short
        trips = []
        for i, day in enumerate(days):
            calc_count += 1
            lots = [l for l in lots if l.expiry > day]
            n = need.get(day, 0.0)
            available = sum(l.qty for l in lots)
            if n > EPS and available + EPS < n:
                if i == 0:
                    out_exceptions.append({"type": "short_today", "ingredient_id": g, "name": ing.name,
                                           "short_base": round(n - available, 3)})
                else:
                    last = min(i + shelf - 1, len(days) - 1)
                    window = [(days[k], need.get(days[k], 0.0)) for k in range(i, last + 1)]
                    window_need = sum(v for _, v in window)
                    s = safety_by.get((g, min(len(window), 7)))
                    buffer = float(s.buffer) if s is not None else DEFAULT_BUFFER
                    target = window_need * (1 + buffer)
                    usable = _usable_in_window(lots, window)
                    calc_count += len(window)
                    packs = math.ceil((target - usable) / ing.pack_size_base - 1e-9)
                    if packs > 0:
                        lots.append(Lot(packs * ing.pack_size_base, day + timedelta(days=shelf)))
                        trips.append(
                            {
                                "date": day.isoformat(),
                                "packs": packs,
                                "buy_base": round(packs * ing.pack_size_base, 3),
                                "window_start": window[0][0].isoformat(),
                                "window_end": window[-1][0].isoformat(),
                                "window_days": len(window),
                                "window_need_base": round(window_need, 3),
                                "buffer_pct": round(buffer * 100, 1),
                                "buffer_base": round(window_need * buffer, 3),
                                "target_base": round(target, 3),
                                "usable_base": round(usable, 3),
                                "service_level": float(s.service_level) if s is not None else None,
                                "n_samples": int(s.n_samples) if s is not None else 0,
                                "method": s.method if s is not None else "default",
                            }
                        )
            _consume(lots, n)

        leftover = sum(l.qty for l in lots if l.expiry > end)
        total_need = sum(need.get(d, 0.0) for d in days[1:])
        if not trips:
            if total_need > EPS:
                covered.append({"ingredient_id": g, "name": ing.name, "need_base": round(total_need, 3),
                                "stock_base": stock_info["qty_base"], "expired": stock_info["expired"]})
            continue

        packs_total = sum(t["packs"] for t in trips)
        win_need = sum(t["window_need_base"] for t in trips)
        buffer_base = sum(t["buffer_base"] for t in trips)
        line = {
            "ingredient_id": g,
            "name": ing.name,
            "supplier_id": ing.supplier_id,
            "base_uom": ing.base_uom,
            "pack_uom": ing.pack_uom,
            "pack_size_base": float(ing.pack_size_base),
            "need_base": round(total_need, 3),
            "today_use_base": round(need.get(today, 0.0), 3),
            "buffer_pct": round(buffer_base / win_need * 100, 1) if win_need > 0 else trips[0]["buffer_pct"],
            "buffer_base": round(buffer_base, 3),
            "usable_stock_base": trips[0]["usable_base"],
            "buy_schedule": [{"date": t["date"], "packs": t["packs"]} for t in trips],
            "suggested_packs": packs_total,
            "pack_price_rm": float(ing.pack_price_rm),
            "line_total_rm": round(packs_total * float(ing.pack_price_rm), 2),
            "leftover_base": round(leftover, 3),
            "explanation": {
                "daily_need": [{"date": d.isoformat(), "need_base": round(need.get(d, 0.0), 3)} for d in days],
                "stock": stock_info,
                "trips": trips,
                "service_level": trips[0]["service_level"],
                "n_samples": trips[0]["n_samples"],
                "method": trips[0]["method"],
                "shelf_life_days": shelf,
                "leftover_base": round(leftover, 3),
            },
        }
        lines_by_supplier.setdefault(ing.supplier_id, []).append(line)

    suppliers, grand_total = [], 0.0
    for sid, lines in lines_by_supplier.items():
        lines.sort(key=lambda l: l["name"])
        sup = sup_by.get(sid)
        subtotal = round(sum(l["line_total_rm"] for l in lines), 2)
        warnings = []
        if sup is not None and 0 < subtotal < float(sup.min_order_rm):
            warnings.append(f"Below the supplier's minimum order of RM {float(sup.min_order_rm):,.2f}")
        grand_total += subtotal
        suppliers.append(
            {
                "supplier_id": sid,
                "name": sup.name if sup is not None else "No supplier set",
                "lines": lines,
                "subtotal_rm": subtotal,
                "min_order_rm": float(sup.min_order_rm) if sup is not None else 0.0,
                "warnings": warnings,
            }
        )
    suppliers.sort(key=lambda s: s["name"])
    return {
        "suppliers": suppliers,
        "discard": discard,
        "covered": covered,
        "grand_total_rm": round(grand_total, 2),
        "exceptions": out_exceptions,
        "calc_count": calc_count,
    }
