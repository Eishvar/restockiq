"""Bringing sales in from a file, and taking wrong sales back out.

The same path serves CSV, Excel and PDF: the file is read into rows, the rows are checked and shown to a person in a
preview (they can fix a date, a number or a dish, or leave a row out), and only then are they saved. The import
never guesses: a dish that is not on the menu is listed and left out until a person maps it, and a row that cannot
be understood is left out with its reason. A PDF is read by AI, so its preview says so and a person checks it.

A day in the file replaces that day's sales. Whatever it replaces, and anything the owner removes, is moved aside
(not destroyed), so it can be restored. "Delete forever" is the only step that really erases sales.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, distinct, func, or_, select
from sqlalchemy.orm import Session

from app.ai import llm
from app.core.activity import log_action
from app.core.clock import now_kl
from app.core.today import get_today
from app.modules.catalog.models import MenuItem
from app.modules.sales.models import SalesDaily
from app.modules.sales_data import parsing
from app.modules.sales_data.models import SalesDailyRemoved, SalesDraft, SalesImport, SalesRemoval
from app.modules.sales_data.schemas import (
    Coverage, ConfirmIn, DraftRow, ImportOut, ImportPreview, ImportResult, RemoveIn, RemovePreview, RemoveResult,
    RemovalOut, SalesOverview, UnmatchedDish,
)
from app.modules.settings.models import Tenant, User
from app.modules.setup.models import TenantSetup

SHOW_LIMIT = 300  # rows shown for checking; a longer file is still saved in full
MAX_PDF_ROWS = 2000
CHUNK = 500


# ---------- small helpers ----------
def _key(text: str) -> str:
    return " ".join(str(text).split()).lower()


def _setup_row(db: Session, tenant_id: int) -> TenantSetup:
    row = db.get(TenantSetup, tenant_id)
    if row is None:
        row = TenantSetup(tenant_id=tenant_id)
        db.add(row)
        db.flush()
    return row


def _touch(db: Session, tenant_id: int) -> None:
    """Remember that sales changed, so plans made earlier can say they used older numbers."""
    _setup_row(db, tenant_id).sales_changed_at = now_kl()


def _menu(db: Session, tenant_id: int) -> list[MenuItem]:
    return list(db.scalars(select(MenuItem).where(MenuItem.tenant_id == tenant_id)))


def _user_names(db: Session, tenant_id: int) -> dict[int, str]:
    return {u.id: u.name for u in db.scalars(select(User).where(User.tenant_id == tenant_id))}


def _chunks(items: list, size: int = CHUNK):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def coverage(db: Session, tenant_id: int) -> Coverage:
    first, last, days, rows = db.execute(
        select(func.min(SalesDaily.date), func.max(SalesDaily.date), func.count(distinct(SalesDaily.date)), func.count())
        .where(SalesDaily.tenant_id == tenant_id)
    ).one()
    return Coverage(first_date=first, last_date=last, days=days or 0, rows=rows or 0)


# ---------- reading and checking rows ----------
def _check_row(row: dict, menu_ids: set[int], today: date) -> None:
    """Set row["problem"] to a plain-words reason, or None when the row can be saved."""
    problem = None
    day = None
    if row.get("date"):
        try:
            day = date.fromisoformat(row["date"])
        except ValueError:
            day = None
    if day is None:
        problem = "date not understood (use YYYY-MM-DD or DD/MM/YYYY)"
    elif day > today:
        problem = f"{day.isoformat()} is after today ({today.isoformat()})"
    elif day.year < 2000:
        problem = "date is too old"
    elif row.get("qty") is None or row["qty"] < 0:
        problem = "quantity must be a whole number, zero or more"
    elif row.get("item_id") not in menu_ids:
        problem = "dish is not on your menu"
    row["problem"] = problem


def _resolve(db: Session, user: User, raw: list[dict]) -> list[dict]:
    """Raw text rows -> checked rows. Nothing is guessed: only an exact code or name matches a dish."""
    menu = _menu(db, user.tenant_id)
    by_code = {_key(m.code): m for m in menu}
    by_name = {_key(m.name): m for m in menu}
    menu_ids = {m.id for m in menu}
    today = get_today(db, user.tenant_id)
    out = []
    for i, r in enumerate(raw):
        day = None
        try:
            day = parsing.parse_date(r["date"]).isoformat()
        except ValueError:
            pass
        qty = None
        try:
            qty = int(float(str(r["qty"]).replace(",", "")))
        except ValueError:
            pass
        item = by_code.get(_key(r.get("code", ""))) if r.get("code") else None
        if item is None and r.get("dish"):
            item = by_name.get(_key(r["dish"]))
        net = None
        text = str(r.get("net", "")).replace(",", "").replace("RM", "").replace("rm", "").strip()
        if text:
            try:
                net = round(float(text), 2)
            except ValueError:
                net = None
        row = {"i": i, "line": r["line"], "date": day, "date_text": str(r["date"]), "dish": r.get("dish") or r.get("code") or "(blank)",
               "item_id": item.id if item else None, "qty": qty, "net": net, "problem": None}
        _check_row(row, menu_ids, today)
        out.append(row)
    return out


class _PdfRow(BaseModel):
    date: str
    dish: str
    qty: int
    amount: float


class PdfRows(BaseModel):
    rows: list[_PdfRow]
    notes: str


def _read_pdf(db: Session, user: User, filename: str, data: bytes) -> tuple[list[dict], str | None]:
    """The AI reads a PDF report into raw rows. A person checks them in the preview before anything is saved."""
    if not llm.pdf_ai_available():
        raise HTTPException(503, "Reading PDF files needs the AI service, which is not available right now. "
                                 "Upload a CSV or Excel file instead.")
    answer = llm.complete_json_with_pdf("sales_pdf", {"today": get_today(db, user.tenant_id).isoformat()}, PdfRows, data, filename)
    if answer is None:
        raise HTTPException(502, "The AI could not read this PDF. It may be too long or too unclear. "
                                 "Try a shorter report, or upload a CSV or Excel file.")
    rows = answer["rows"][:MAX_PDF_ROWS]
    if not rows:
        raise HTTPException(422, "The AI found no sales lines in this PDF. " + (answer["notes"] or "Check that it is a sales report."))
    raw = [{"line": n, "date": r["date"], "code": "", "dish": r["dish"], "qty": str(r["qty"]),
            "net": str(r["amount"]) if r["amount"] > 0 else ""} for n, r in enumerate(rows, start=1)]
    return raw, (answer["notes"] or None)


# ---------- preview ----------
def _summary(db: Session, tenant_id: int, rows: list[dict]) -> dict:
    good = [r for r in rows if r["problem"] is None]
    days = sorted({r["date"] for r in good})
    have = set()
    if days:
        have = {d.isoformat() for d in db.scalars(
            select(SalesDaily.date).where(SalesDaily.tenant_id == tenant_id, SalesDaily.date.in_([date.fromisoformat(d) for d in days])).distinct())}
    unmatched: dict[str, int] = defaultdict(int)
    for r in rows:
        if r["item_id"] is None:
            unmatched[r["dish"]] += 1
    return {
        "rows_total": len(rows), "rows_ok": len(good), "problems": len(rows) - len(good), "days": len(days),
        "date_from": date.fromisoformat(days[0]) if days else None, "date_to": date.fromisoformat(days[-1]) if days else None,
        "new_days": len([d for d in days if d not in have]), "replaced_days": len([d for d in days if d in have]),
        "dishes_sold": int(sum(r["qty"] for r in good)), "net_sales_rm": round(sum(r["net"] or 0 for r in good), 2),
        "unmatched": [UnmatchedDish(dish=n, rows=c) for n, c in sorted(unmatched.items(), key=lambda x: -x[1])[:30]],
    }


def _preview(db: Session, draft: SalesDraft) -> ImportPreview:
    rows = draft.rows
    shown = sorted(rows, key=lambda r: (r["problem"] is None, r["i"]))[:SHOW_LIMIT]
    return ImportPreview(
        draft_id=draft.id, filename=draft.filename, kind=draft.kind, read_by_ai=draft.read_by_ai, notes=draft.notes,
        rows=[DraftRow(**{k: r[k] for k in ("i", "line", "date", "date_text", "dish", "item_id", "qty", "net", "problem")}) for r in shown],
        rows_shown=len(shown), **_summary(db, draft.tenant_id, rows),
    )


def preview_file(db: Session, user: User, filename: str, data: bytes) -> ImportPreview:
    """Read a CSV, Excel or PDF file and keep the result as a draft for a person to check. Saves no sales."""
    filename = (filename or "sales").strip()[:200]
    if len(data) > parsing.MAX_BYTES:
        raise HTTPException(413, "That file is too big. Upload a shorter date range.")
    kind = parsing.kind_of(filename)
    notes = None
    if kind == "pdf":
        raw, notes = _read_pdf(db, user, filename, data)
    else:
        kind, raw = parsing.read_rows(filename, data)
    rows = _resolve(db, user, raw)
    cutoff = now_kl() - timedelta(days=1)
    db.execute(delete(SalesDraft).where(SalesDraft.tenant_id == user.tenant_id, SalesDraft.ts < cutoff))  # old, unused drafts
    draft = SalesDraft(tenant_id=user.tenant_id, user_id=user.id, ts=now_kl(), filename=filename, kind=kind,
                       read_by_ai=kind == "pdf", notes=(notes or "")[:500] or None, rows=rows)
    db.add(draft)
    db.commit()
    return _preview(db, draft)


# ---------- confirm ----------
def _archive(db: Session, user: User, rows: list[SalesDaily], label: str, import_id: int | None = None) -> SalesRemoval:
    """Move sales rows aside so they can be restored. Every screen reads sales_daily, so they stop counting at once."""
    days = sorted({r.date for r in rows})
    removal = SalesRemoval(tenant_id=user.tenant_id, ts=now_kl(), user_id=user.id, label=label[:200], date_from=days[0],
                           date_to=days[-1], days=len(days), rows=len(rows), import_id=import_id)
    db.add(removal)
    db.flush()
    db.add_all(
        SalesDailyRemoved(tenant_id=user.tenant_id, removal_id=removal.id, date=r.date, menu_item_id=r.menu_item_id, qty=r.qty,
                          net_sales_rm=r.net_sales_rm, import_id=r.import_id)
        for r in rows
    )
    for part in _chunks([r.id for r in rows]):
        db.execute(delete(SalesDaily).where(SalesDaily.id.in_(part)))
    return removal


def confirm(db: Session, user: User, body: ConfirmIn) -> tuple[ImportResult, bool]:
    """Save a checked draft. Returns (result, enough_new_days_to_remeasure_buffers)."""
    draft = db.get(SalesDraft, body.draft_id)
    if draft is None or draft.tenant_id != user.tenant_id:
        raise HTTPException(404, "That preview has expired. Upload the file again.")
    menu = _menu(db, user.tenant_id)
    menu_ids = {m.id for m in menu}
    price = {m.id: m.price_rm for m in menu}
    today = get_today(db, user.tenant_id)
    rows = [dict(r) for r in draft.rows]

    mapping = {_key(k): v for k, v in body.dish_map.items()}
    for r in rows:
        if r["item_id"] is None and mapping.get(_key(r["dish"])) in menu_ids:
            r["item_id"] = mapping[_key(r["dish"])]
    dropped: set[int] = set()
    for e in body.edits:
        if not 0 <= e.i < len(rows):
            continue
        r = rows[e.i]
        if e.drop:
            dropped.add(e.i)
            continue
        if e.date is not None:
            try:
                r["date"] = parsing.parse_date(e.date).isoformat()
            except ValueError:
                r["date"] = None
        if e.item_id is not None:
            r["item_id"] = e.item_id
        if e.qty is not None:
            r["qty"] = e.qty
        if e.net is not None:
            r["net"] = e.net
    rows = [r for r in rows if r["i"] not in dropped]
    for r in rows:
        _check_row(r, menu_ids, today)
    good = [r for r in rows if r["problem"] is None]
    if not good:
        raise HTTPException(422, "Nothing in this file can be saved yet. Fix the rows marked in red, or map the dishes.")

    groups: dict[tuple[str, int], list[float]] = defaultdict(lambda: [0, 0.0])
    for r in good:
        slot = groups[(r["date"], r["item_id"])]
        slot[0] += r["qty"]
        slot[1] += r["net"] if r["net"] is not None else r["qty"] * price[r["item_id"]]
    days = sorted({date.fromisoformat(d) for d, _ in groups})

    existing = list(db.scalars(select(SalesDaily).where(SalesDaily.tenant_id == user.tenant_id, SalesDaily.date.in_(days))))
    replaced = len({r.date for r in existing})
    if existing:
        _archive(db, user, existing, f"Replaced by {draft.filename}")
    record = SalesImport(tenant_id=user.tenant_id, ts=now_kl(), user_id=user.id, filename=draft.filename, kind=draft.kind,
                         read_by_ai=draft.read_by_ai, date_from=days[0], date_to=days[-1], days=len(days),
                         rows=len([g for g in groups.values() if g[0] > 0]),
                         skipped={"left_out": len(draft.rows) - len(good), "dropped": len(dropped)})
    db.add(record)
    db.flush()
    db.add_all(
        SalesDaily(tenant_id=user.tenant_id, date=date.fromisoformat(d), menu_item_id=item_id, qty=int(q), net_sales_rm=round(net, 2),
                   import_id=record.id)
        for (d, item_id), (q, net) in groups.items() if q > 0  # a zero row means "not sold": same as no row
    )
    _touch(db, user.tenant_id)
    new_days = len(days) - replaced
    log_action(db, user, "sales_imported", "sales_import", record.id,
               {"file": draft.filename, "type": draft.kind, "read_by_ai": draft.read_by_ai, "date_from": days[0].isoformat(),
                "date_to": days[-1].isoformat(), "days": len(days), "new_days": new_days, "replaced_days": replaced,
                "rows_left_out": len(draft.rows) - len(good)})
    db.delete(draft)
    db.commit()
    result = ImportResult(
        import_id=record.id, filename=draft.filename, days=len(days), rows_saved=record.rows, rows_left_out=len(draft.rows) - len(good),
        new_days=new_days, replaced_days=replaced, dishes_sold=int(sum(g[0] for g in groups.values())),
        net_sales_rm=round(sum(g[1] for g in groups.values()), 2), date_from=days[0], date_to=days[-1],
        today=get_today(db, user.tenant_id),
    )
    return result, new_days >= 7


# ---------- remove, restore, delete forever ----------
def _target(db: Session, user: User, body: RemoveIn) -> tuple[list[SalesDaily], str, int | None, SalesImport | None]:
    tid = user.tenant_id
    if body.import_id is not None:
        imp = db.get(SalesImport, body.import_id)
        if imp is None or imp.tenant_id != tid:
            raise HTTPException(404, "That file was not found")
        if imp.status != "active":
            raise HTTPException(409, "That file has already been removed")
        rows = list(db.scalars(select(SalesDaily).where(SalesDaily.tenant_id == tid, SalesDaily.import_id == imp.id)))
        label, import_id = f"File {imp.filename}", imp.id
    elif body.date_from is not None and body.date_to is not None:
        if body.date_to < body.date_from:
            raise HTTPException(422, "The last day must not be before the first day")
        rows = list(db.scalars(select(SalesDaily).where(SalesDaily.tenant_id == tid, SalesDaily.date >= body.date_from,
                                                        SalesDaily.date <= body.date_to)))
        label = f"Day {body.date_from.isoformat()}" if body.date_from == body.date_to else f"Days {body.date_from.isoformat()} to {body.date_to.isoformat()}"
        import_id, imp = None, None
    else:
        raise HTTPException(422, "Choose a file to remove, or a range of days")
    if not rows:
        raise HTTPException(409, "There are no sales to remove there")
    return rows, label, import_id, imp


def remove_preview(db: Session, user: User, body: RemoveIn) -> RemovePreview:
    rows, label, import_id, _ = _target(db, user, body)
    days = sorted({r.date for r in rows})
    tenant = db.get(Tenant, user.tenant_id)
    today_now = get_today(db, user.tenant_id)
    today_after = None
    if not (tenant and tenant.today_override):  # with a demo date set, "today" does not move
        if import_id is not None:
            stays = or_(SalesDaily.import_id.is_(None), SalesDaily.import_id != import_id)
        else:
            stays = or_(SalesDaily.date < body.date_from, SalesDaily.date > body.date_to)
        latest = db.scalar(select(func.max(SalesDaily.date)).where(SalesDaily.tenant_id == user.tenant_id, stays))
        today_after = latest + timedelta(days=1) if latest else None
    return RemovePreview(label=label, date_from=days[0], date_to=days[-1], days=len(days), rows=len(rows),
                         today_now=today_now, today_after=today_after)


def _removal_out(r: SalesRemoval, names: dict[int, str]) -> RemovalOut:
    return RemovalOut(id=r.id, ts=r.ts, label=r.label, date_from=r.date_from, date_to=r.date_to, days=r.days, rows=r.rows,
                      user_name=names.get(r.user_id))


def remove(db: Session, user: User, body: RemoveIn) -> RemoveResult:
    rows, label, import_id, imp = _target(db, user, body)
    removal = _archive(db, user, rows, label, import_id)
    if imp is not None:
        imp.status = "removed"
    _touch(db, user.tenant_id)
    log_action(db, user, "sales_removed", "sales_removal", removal.id,
               {"what": label, "days": removal.days, "rows": removal.rows, "date_from": removal.date_from.isoformat(),
                "date_to": removal.date_to.isoformat()})
    db.commit()
    return RemoveResult(removal=_removal_out(removal, _user_names(db, user.tenant_id)), today=get_today(db, user.tenant_id))


def _removal(db: Session, user: User, removal_id: int) -> SalesRemoval:
    r = db.get(SalesRemoval, removal_id)
    if r is None or r.tenant_id != user.tenant_id:
        raise HTTPException(404, "That removed sales entry was not found")
    if r.restored_at is not None:
        raise HTTPException(409, "That has already been restored")
    if r.purged_at is not None:
        raise HTTPException(409, "That has been deleted forever")
    return r


def restore(db: Session, user: User, removal_id: int) -> RemoveResult:
    r = _removal(db, user, removal_id)
    held = list(db.scalars(select(SalesDailyRemoved).where(SalesDailyRemoved.removal_id == r.id)))
    days = sorted({h.date for h in held})
    busy = sorted({d for d in db.scalars(select(SalesDaily.date).where(SalesDaily.tenant_id == user.tenant_id, SalesDaily.date.in_(days)).distinct())})
    if busy:
        raise HTTPException(409, f"There are already sales for {len(busy)} of these days (the first is {busy[0].isoformat()}). "
                                 "Remove those first, then restore this.")
    db.add_all(SalesDaily(tenant_id=user.tenant_id, date=h.date, menu_item_id=h.menu_item_id, qty=h.qty,
                          net_sales_rm=h.net_sales_rm, import_id=h.import_id) for h in held)
    for part in _chunks([h.id for h in held]):
        db.execute(delete(SalesDailyRemoved).where(SalesDailyRemoved.id.in_(part)))
    r.restored_at = now_kl()
    if r.import_id is not None:
        imp = db.get(SalesImport, r.import_id)
        if imp is not None:
            imp.status = "active"
    _touch(db, user.tenant_id)
    log_action(db, user, "sales_restored", "sales_removal", r.id, {"what": r.label, "days": r.days, "rows": r.rows})
    db.commit()
    return RemoveResult(removal=_removal_out(r, _user_names(db, user.tenant_id)), today=get_today(db, user.tenant_id))


def delete_forever(db: Session, user: User, removal_id: int) -> RemovalOut:
    r = _removal(db, user, removal_id)
    db.execute(delete(SalesDailyRemoved).where(SalesDailyRemoved.removal_id == r.id))
    r.purged_at = now_kl()
    log_action(db, user, "sales_deleted_forever", "sales_removal", r.id, {"what": r.label, "days": r.days, "rows": r.rows})
    db.commit()
    return _removal_out(r, _user_names(db, user.tenant_id))


# ---------- overview ----------
def overview(db: Session, user: User) -> SalesOverview:
    tid = user.tenant_id
    names = _user_names(db, tid)
    tenant = db.get(Tenant, tid)
    imports = list(db.scalars(select(SalesImport).where(SalesImport.tenant_id == tid).order_by(SalesImport.id.desc()).limit(30)))
    removed = list(db.scalars(select(SalesRemoval).where(SalesRemoval.tenant_id == tid, SalesRemoval.restored_at.is_(None),
                                                         SalesRemoval.purged_at.is_(None)).order_by(SalesRemoval.id.desc()).limit(30)))
    return SalesOverview(
        coverage=coverage(db, tid), today=get_today(db, tid), today_is_demo_date=bool(tenant and tenant.today_override),
        imports=[ImportOut(id=i.id, ts=i.ts, filename=i.filename, kind=i.kind, read_by_ai=i.read_by_ai, date_from=i.date_from,
                           date_to=i.date_to, days=i.days, rows=i.rows, status=i.status, user_name=names.get(i.user_id)) for i in imports],
        removed=[_removal_out(r, names) for r in removed], ai_available=llm.pdf_ai_available(),
    )


TEMPLATE_CSV = "Date,Item Code,Item Name,Qty Sold,Net Sales (RM)\n2026-10-21,M001,White rice,40,48.00\n2026-10-21,M002,Telur Dadar,25,37.50\n"
