"""First-time setup: country (currency + public holidays), sales history, stock, recipes, optional calendar.

The wizard order is country -> sales -> inventory -> recipes -> calendar. Each step stores its own result, and
`status()` derives which step is next, so a refresh or a different browser resumes in the right place.
"""
import csv
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.activity import log_action
from app.core.clock import now_kl
from app.modules.calendar.models import CalendarEvent
from app.modules.catalog import recipes
from app.modules.sales_data import service as sales_service
from app.modules.setup.models import TenantSetup
from app.modules.setup.schemas import CountryResult, SetupStatus
from app.modules.settings.models import Tenant, User

# Only Malaysia for now. Adding a country = one more entry here plus its holiday file in data/.
COUNTRIES = {"MY": {"name": "Malaysia", "currency": "MYR", "holidays": "calendar_my.csv"}}


def get_setup(db: Session, tenant_id: int) -> TenantSetup:
    row = db.get(TenantSetup, tenant_id)
    if row is None:
        row = TenantSetup(tenant_id=tenant_id)
        db.add(row)
        db.flush()
    return row


def status(db: Session, tenant_id: int) -> SetupStatus:
    row = get_setup(db, tenant_id)
    tenant = db.get(Tenant, tenant_id)
    inventory_done = tenant.onboarded_at is not None
    if row.country is None:
        step = "country"
    elif row.setup_done_at is None and row.sales_confirmed_at is None:
        step = "sales"  # a business that finished setup before this step existed is not sent back to it
    elif not inventory_done:
        step = "inventory"
    elif row.setup_done_at is None and row.recipes_confirmed_at is None:
        step = "recipes"  # a business that finished setup before this step existed is not sent back to it
    elif row.setup_done_at is None:
        step = "calendar"
    else:
        step = "done"
    country = COUNTRIES.get(row.country or "")
    return SetupStatus(
        step=step,
        complete=step == "done",
        country=row.country,
        country_name=country["name"] if country else None,
        currency=row.currency,
        sales_done=row.sales_confirmed_at is not None or row.setup_done_at is not None,
        inventory_done=inventory_done,
        recipes_done=row.recipes_confirmed_at is not None or row.setup_done_at is not None,
        calendar_skipped=row.calendar_skipped,
    )


def _import_holidays(db: Session, tenant_id: int, filename: str) -> tuple[int, int]:
    """Add the country's public holidays that the calendar does not have yet. Returns (added, already there)."""
    with open(settings.data_dir / filename, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    have = {
        (e.type, e.start_date)
        for e in db.scalars(select(CalendarEvent).where(CalendarEvent.tenant_id == tenant_id, CalendarEvent.type == "public_holiday"))
    }
    added = 0
    for r in rows:
        start = date.fromisoformat(r["start_date"])
        if (r["type"], start) in have:
            continue
        db.add(
            CalendarEvent(
                tenant_id=tenant_id, type=r["type"], label=r["label"] or None, start_date=start,
                end_date=date.fromisoformat(r["end_date"]), name=r["name"], status="approved", source="setup",
            )
        )
        have.add((r["type"], start))
        added += 1
    return added, len(rows) - added


def choose_country(db: Session, user: User, code: str) -> CountryResult:
    country = COUNTRIES.get(code.upper())
    if country is None:
        raise HTTPException(422, "Only Malaysia is available in this version")
    row = get_setup(db, user.tenant_id)
    row.country, row.currency = code.upper(), country["currency"]
    added, there = _import_holidays(db, user.tenant_id, country["holidays"])
    log_action(
        db, user, "setup_country_chosen", "tenant", user.tenant_id,
        {"country": row.country, "currency": row.currency, "holidays_added": added, "holidays_already_there": there},
    )
    db.commit()
    return CountryResult(status=status(db, user.tenant_id), holidays_added=added, holidays_already_there=there)


MIN_SALES_DAYS = 28  # four weeks is the least the forecast can learn a weekday pattern from


def confirm_sales(db: Session, user: User) -> SetupStatus:
    """Step 2 (not optional): there must be enough sales history to forecast from. The demo's is already loaded."""
    current = status(db, user.tenant_id)
    if current.step == "country":
        raise HTTPException(409, "Finish the 'country' step first")
    row = get_setup(db, user.tenant_id)
    if row.sales_confirmed_at is None:
        have = sales_service.coverage(db, user.tenant_id)
        if have.days < MIN_SALES_DAYS:
            raise HTTPException(409, f"Add at least {MIN_SALES_DAYS} days of sales first (you have {have.days}). "
                                     "Upload a CSV, Excel or PDF sales report.")
        row.sales_confirmed_at = now_kl()
        log_action(db, user, "setup_sales_confirmed", "tenant", user.tenant_id,
                   {"days": have.days, "date_from": have.first_date.isoformat(), "date_to": have.last_date.isoformat()})
    db.commit()
    return status(db, user.tenant_id)


def confirm_recipes(db: Session, user: User) -> SetupStatus:
    """Step 4 (not optional): every dish on the menu must have a recipe before the wizard can go on."""
    current = status(db, user.tenant_id)
    if current.step in ("country", "sales", "inventory"):
        raise HTTPException(409, f"Finish the '{current.step}' step first")
    row = get_setup(db, user.tenant_id)
    if row.recipes_confirmed_at is None:
        missing = recipes.dishes_without_recipe(db, user.tenant_id)
        if missing:
            shown = ", ".join(missing[:5]) + ("…" if len(missing) > 5 else "")
            raise HTTPException(409, f"{len(missing)} dish(es) still have no recipe: {shown}")
        row.recipes_confirmed_at = now_kl()
        log_action(db, user, "setup_recipes_confirmed", "tenant", user.tenant_id,
                   {"dishes": len(recipes.recipe_book(db, user)), "changed_by_hand": recipes.recipes_edited(db, user.tenant_id)})
    db.commit()
    return status(db, user.tenant_id)


def complete(db: Session, user: User, skip_calendar: bool) -> SetupStatus:
    """Finish the wizard. Needs country, sales, stock and recipes done; the calendar step may be skipped."""
    current = status(db, user.tenant_id)
    if current.step in ("country", "sales", "inventory", "recipes"):
        raise HTTPException(409, f"Finish the '{current.step}' step first")
    row = get_setup(db, user.tenant_id)
    if row.setup_done_at is None:
        row.calendar_skipped = skip_calendar
        row.setup_done_at = now_kl()
        log_action(db, user, "setup_completed", "tenant", user.tenant_id, {"calendar_skipped": skip_calendar})
    db.commit()
    return status(db, user.tenant_id)
