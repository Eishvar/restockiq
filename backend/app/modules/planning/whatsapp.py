"""Order text for WhatsApp, and the trip schedule after the manager edits the pack counts. Pure functions."""
import re
from datetime import date
from urllib.parse import quote

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


def whatsapp_number(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    return digits or None


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


def whatsapp_url(number: str | None, text: str) -> str | None:
    return f"https://wa.me/{number}?text={quote(text)}" if number else None
