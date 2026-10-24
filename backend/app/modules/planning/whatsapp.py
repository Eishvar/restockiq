"""Order text for WhatsApp, and the trip schedule after the manager edits the pack counts. Pure functions."""
from datetime import date
from urllib.parse import quote

from app.core.phone import international_number as whatsapp_number
from app.core.units import format_packs


def effective_schedule(schedule: list[dict], suggested: int, final: int) -> list[dict]:
    """Spread the edited pack count over the planned trips.

    Extra packs go on the first trip; removed packs come off the latest trips first.
    """
    trips = [{"date": t["date"], "packs": t["packs"]} for t in schedule]
    delta = final - suggested
    if delta > 0 and trips:
        trips[0]["packs"] += delta
    elif delta < 0:
        for t in reversed(trips):
            take = min(t["packs"], -delta)
            t["packs"] -= take
            delta += take
            if delta == 0:
                break
    return [t for t in trips if t["packs"] > 0]


def _day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}"


def call_url(number: str | None) -> str | None:
    return f"tel:+{number}" if number else None


def build_order_message(supplier_name: str, tenant_name: str, lines: list[dict], total_rm: float) -> str:
    """lines: name, pack_uom, schedule [{date, packs}]. One block per delivery date for items bought in trips."""
    by_date: dict[str, list[str]] = {}
    for line in lines:
        for trip in line["schedule"]:
            by_date.setdefault(trip["date"], []).append(f"- {line['name']} – {format_packs(trip['packs'], line['pack_uom'])}")
    parts = [f"Hello {supplier_name}, this is {tenant_name}."]
    for iso in sorted(by_date):
        parts.append(f"Order for {_day(iso)}:")
        parts.extend(sorted(by_date[iso]))
    parts.append(f"Total: RM {total_rm:,.2f}")
    parts.append(f"Thank you! – {tenant_name}")
    return "\n".join(parts)


def build_order_note(po_id: int, supplier_name: str, tenant_name: str, order_date: date, lines: list[dict],
                     total_rm: float) -> str:
    """The note sent to the supplier (a purchase order, not a tax invoice; RestockAI never pays or files anything).

    lines: name, pack_uom, pack_price_rm, schedule [{date, packs}]. One block per delivery day, each line with its
    price and line total, then the order total.
    """
    by_date: dict[str, list[tuple[str, int, str, float]]] = {}
    for line in lines:
        for trip in line["schedule"]:
            by_date.setdefault(trip["date"], []).append((line["name"], trip["packs"], line["pack_uom"], line["pack_price_rm"]))
    parts = [
        f"PURCHASE ORDER PO-{po_id:04d}",
        f"From: {tenant_name}",
        f"To: {supplier_name}",
        f"Date: {_day(order_date.isoformat())} {order_date.year}",
        "",
    ]
    for iso in sorted(by_date):
        parts.append(f"Delivery on {_day(iso)}:")
        subtotal = 0.0
        for n, (name, packs, uom, price) in enumerate(sorted(by_date[iso]), start=1):
            subtotal += packs * price
            parts.append(f"{n}. {name} - {format_packs(packs, uom)} x RM {price:,.2f} = RM {packs * price:,.2f}")
        if len(by_date) > 1:
            parts.append(f"Subtotal for this delivery: RM {subtotal:,.2f}")
        parts.append("")
    parts += [
        f"ORDER TOTAL: RM {total_rm:,.2f}",
        "",
        "Please confirm that you can supply this and the delivery time. Thank you!",
        f"- {tenant_name}",
    ]
    return "\n".join(parts)


def whatsapp_url(number: str | None, text: str) -> str | None:
    return f"https://wa.me/{number}?text={quote(text, safe='')}" if number else None
