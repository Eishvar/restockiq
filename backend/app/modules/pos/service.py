"""POS connection and the sales-file import.

The import never guesses: dishes that are not on the menu are listed and left out, bad rows are listed and
skipped, and a person confirms the summary before anything is saved. A day that appears in the file replaces
that day's sales, so re-uploading a corrected export is safe.
"""
import io
import re
from collections import defaultdict
from datetime import date, timedelta

import pandas as pd
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.activity import log_action
from app.core.clock import now_kl
from app.core.today import get_today
from app.modules.catalog.models import MenuItem
from app.modules.pos import feedme
from app.modules.pos.models import PosImport
from app.modules.pos.schemas import (
    BadRow, FeedMeDay, FeedMePreview, ImportSummary, LastImport, PosStatus, Unmatched,
)
from app.modules.sales.models import SalesDaily
from app.modules.setup.service import get_setup
from app.modules.settings.models import User

PROVIDERS = {"feedme": "FeedMe"}
MAX_BAD_ROWS_SHOWN = 10
MAX_FILE_CHARS = 8_000_000

# Header names are compared in lower case with everything but letters and digits removed.
ALIASES = {
    "date": {"date", "salesdate", "businessdate"},
    "code": {"itemcode", "itemid", "code", "sku"},
    "name": {"itemname", "item", "name", "product"},
    "qty": {"qtysold", "qty", "quantity", "quantitysold"},
    "unit": {"unitpricerm", "unitprice", "price"},
    "net": {"netsalesrm", "netsales", "total", "amount"},
}


def _norm(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", header.lower())


def _parse_date(text: str) -> date:
    text = text.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return date.fromisoformat(text)
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", text):
        d, m, y = (int(p) for p in text.split("/"))
        return date(y, m, d)  # Malaysian order: day/month/year
    raise ValueError("date not understood (use YYYY-MM-DD or DD/MM/YYYY)")


def connect(db: Session, user: User, provider: str) -> PosStatus:
    if provider not in PROVIDERS:
        raise HTTPException(422, "Only FeedMe is available in this version")
    row = get_setup(db, user.tenant_id)
    row.pos_provider, row.pos_connected_at = provider, now_kl()
    log_action(db, user, "pos_connected", "tenant", user.tenant_id, {"provider": provider, "mode": "simulated"})
    db.commit()
    return status(db, user)


def _latest_sales_date(db: Session, tenant_id: int) -> date | None:
    return db.scalar(select(func.max(SalesDaily.date)).where(SalesDaily.tenant_id == tenant_id))


def status(db: Session, user: User) -> PosStatus:
    tid = user.tenant_id
    setup = get_setup(db, tid)
    today = get_today(db, tid)
    latest = _latest_sales_date(db, tid)
    last = db.scalars(select(PosImport).where(PosImport.tenant_id == tid).order_by(PosImport.id.desc())).first()
    uploader = db.get(User, last.user_id) if last and last.user_id else None
    return PosStatus(
        provider=setup.pos_provider,
        connected_at=setup.pos_connected_at,
        latest_sales_date=latest,
        today=today,
        next_to_import=today if (latest is None or latest < today) else None,
        last_import=None if last is None else LastImport(
            ts=last.ts, filename=last.filename, date_from=last.date_from, date_to=last.date_to,
            days=last.days, rows=last.rows, user_name=uploader.name if uploader else None,
        ),
    )


# ---- reading a file --------------------------------------------------------------------------------------

class _Parsed:
    def __init__(self):
        self.total = 0
        self.good: dict[tuple[date, int], list[float]] = defaultdict(lambda: [0, 0.0])  # (day, menu id) -> [qty, net]
        self.unmatched: dict[str, int] = defaultdict(int)
        self.bad: list[BadRow] = []
        self.bad_count = 0

    def reject(self, line: int, reason: str):
        self.bad_count += 1
        if len(self.bad) < MAX_BAD_ROWS_SHOWN:
            self.bad.append(BadRow(line=line, reason=reason))


def _parse(db: Session, user: User, csv_text: str) -> _Parsed:
    if len(csv_text) > MAX_FILE_CHARS:
        raise HTTPException(413, "That file is too big. Export a shorter date range.")
    try:
        frame = pd.read_csv(io.StringIO(csv_text), dtype=str, keep_default_na=False, skipinitialspace=True)
    except Exception:
        raise HTTPException(422, "That does not look like a CSV file") from None

    cols: dict[str, str] = {}
    for original in frame.columns:
        for key, names in ALIASES.items():
            if _norm(str(original)) in names and key not in cols:
                cols[key] = original
    missing = [k for k in ("date", "qty") if k not in cols]
    if missing or not ({"code", "name"} & cols.keys()):
        raise HTTPException(
            422,
            "The file needs these columns: Date, Item Code or Item Name, and Qty Sold. "
            f"Found: {', '.join(map(str, frame.columns)) or 'none'}",
        )

    menu = list(db.scalars(select(MenuItem).where(MenuItem.tenant_id == user.tenant_id)))
    by_code = {m.code.lower(): m for m in menu}
    by_name = {m.name.strip().lower(): m for m in menu}
    today = get_today(db, user.tenant_id)

    out = _Parsed()
    for i, rec in enumerate(frame.to_dict("records"), start=2):  # line 1 is the header
        out.total += 1
        try:
            day = _parse_date(rec[cols["date"]])
        except ValueError as e:
            out.reject(i, str(e))
            continue
        if day > today:
            out.reject(i, f"{day.isoformat()} is after today ({today.isoformat()})")
            continue
        if day.year < 2000:
            out.reject(i, "date is too old")
            continue
        try:
            qty = int(float(rec[cols["qty"]].replace(",", "")))
            if qty < 0:
                raise ValueError
        except ValueError:
            out.reject(i, "quantity must be a whole number, zero or more")
            continue
        item = None
        if "code" in cols and rec[cols["code"]].strip():
            item = by_code.get(rec[cols["code"]].strip().lower())
        if item is None and "name" in cols and rec[cols["name"]].strip():
            item = by_name.get(rec[cols["name"]].strip().lower())
        if item is None:
            label = rec[cols["name"]].strip() if "name" in cols else ""
            label = label or (rec[cols["code"]].strip() if "code" in cols else "")
            out.unmatched[label or "(blank)"] += 1
            continue
        net_text = rec[cols["net"]].strip().replace(",", "") if "net" in cols else ""
        if net_text:
            try:
                net = float(net_text)
            except ValueError:
                out.reject(i, "sales amount is not a number")
                continue
        else:
            net = round(qty * item.price_rm, 2)
        slot = out.good[(day, item.id)]
        slot[0] += qty
        slot[1] += net
    return out


def _summary(db: Session, user: User, parsed: _Parsed) -> ImportSummary:
    days = sorted({d for d, _ in parsed.good})
    have = set()
    if days:
        have = set(
            db.scalars(
                select(SalesDaily.date).where(SalesDaily.tenant_id == user.tenant_id, SalesDaily.date.in_(days)).distinct()
            )
        )
    return ImportSummary(
        rows_total=parsed.total,
        rows_ok=len(parsed.good),
        days=len(days),
        date_from=days[0] if days else None,
        date_to=days[-1] if days else None,
        new_days=len([d for d in days if d not in have]),
        replaced_days=len([d for d in days if d in have]),
        dishes_sold=int(sum(v[0] for v in parsed.good.values())),
        net_sales_rm=round(sum(v[1] for v in parsed.good.values()), 2),
        unmatched=[Unmatched(name=n, rows=c) for n, c in sorted(parsed.unmatched.items(), key=lambda x: -x[1])[:20]],
        bad_count=parsed.bad_count,
        bad_rows=parsed.bad,
    )


def preview(db: Session, user: User, csv_text: str) -> ImportSummary:
    return _summary(db, user, _parse(db, user, csv_text))


def apply_import(db: Session, user: User, filename: str, csv_text: str) -> tuple[ImportSummary, bool]:
    """Save the file's sales. Returns (summary, enough_new_days_to_remeasure_buffers)."""
    setup = get_setup(db, user.tenant_id)
    if setup.pos_provider is None:
        raise HTTPException(409, "Connect your POS first")
    parsed = _parse(db, user, csv_text)
    summary = _summary(db, user, parsed)
    if not parsed.good:
        raise HTTPException(422, "Nothing in this file could be imported. Check the summary for the reasons.")

    days = sorted({d for d, _ in parsed.good})
    db.execute(delete(SalesDaily).where(SalesDaily.tenant_id == user.tenant_id, SalesDaily.date.in_(days)))
    db.add_all(
        SalesDaily(tenant_id=user.tenant_id, date=day, menu_item_id=item_id, qty=int(q), net_sales_rm=round(net, 2))
        for (day, item_id), (q, net) in parsed.good.items()
        if q > 0  # a zero row means "not sold": same as no row
    )
    record = PosImport(
        tenant_id=user.tenant_id, ts=now_kl(), user_id=user.id, provider=setup.pos_provider,
        filename=filename[:200], date_from=days[0], date_to=days[-1], days=len(days), rows=len(parsed.good),
        skipped={"unmatched": [u.model_dump() for u in summary.unmatched], "bad_rows": summary.bad_count},
    )
    db.add(record)
    db.flush()
    log_action(
        db, user, "sales_imported", "pos_import", record.id,
        {
            "provider": setup.pos_provider, "file": filename, "date_from": days[0].isoformat(),
            "date_to": days[-1].isoformat(), "days": len(days), "new_days": summary.new_days,
            "replaced_days": summary.replaced_days, "left_out_dishes": len(summary.unmatched), "bad_rows": summary.bad_count,
        },
    )
    db.commit()
    return summary, summary.new_days >= 7


# ---- the simulated FeedMe screen -------------------------------------------------------------------------

def _check_range(db: Session, user: User, start: date, end: date) -> date:
    cap = get_today(db, user.tenant_id)
    if end < start:
        raise HTTPException(422, "The 'to' date must not be before the 'from' date")
    if end > cap:
        raise HTTPException(422, f"The simulated till only has sales up to {cap.isoformat()}")
    if (end - start).days > 400:
        raise HTTPException(422, "Pick a shorter range (at most about a year)")
    return cap


def feedme_days(db: Session, user: User, count: int = 10) -> list[FeedMeDay]:
    """The last `count` days the simulated till has, newest first, with a flag for days already in RestockAI."""
    cap = get_today(db, user.tenant_id)
    start = cap - timedelta(days=count - 1)
    rows = feedme.export_rows(settings.data_dir, start, cap)
    have = set(
        db.scalars(select(SalesDaily.date).where(SalesDaily.tenant_id == user.tenant_id, SalesDaily.date >= start).distinct())
    )
    daily = rows.assign(_net=rows["Net Sales (RM)"].astype(float)).groupby("Date").agg(
        dishes=("Qty Sold", "sum"), net=("_net", "sum")
    )
    out = []
    for text, r in daily.iterrows():
        day = date.fromisoformat(text)
        out.append(FeedMeDay(date=day, dishes=int(r.dishes), net_sales_rm=round(float(r.net), 2), imported=day in have))
    return sorted(out, key=lambda d: d.date, reverse=True)


def feedme_preview(db: Session, user: User, start: date, end: date, limit: int = 40) -> FeedMePreview:
    _check_range(db, user, start, end)
    rows = feedme.export_rows(settings.data_dir, start, end)
    return FeedMePreview(
        columns=feedme.COLUMNS, rows=rows.head(limit).astype(str).values.tolist(),
        total_rows=len(rows), date_from=start, date_to=end,
    )


def feedme_csv(db: Session, user: User, start: date, end: date) -> tuple[str, str]:
    _check_range(db, user, start, end)
    csv_text = feedme.to_csv(feedme.export_rows(settings.data_dir, start, end))
    log_action(db, user, "pos_export_downloaded", "tenant", user.tenant_id,
               {"provider": "feedme", "mode": "simulated", "date_from": start.isoformat(), "date_to": end.isoformat()})
    db.commit()
    return f"feedme_simulated_sales_{start.isoformat()}_to_{end.isoformat()}.csv", csv_text
