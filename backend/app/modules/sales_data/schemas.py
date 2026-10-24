from datetime import date, datetime

from pydantic import BaseModel, Field


class DraftRow(BaseModel):
    i: int  # position in the draft; edits refer to it
    line: int  # line in the file (or the order the AI read it in)
    date: str | None  # ISO date, or None when it could not be read
    date_text: str  # the date as it was written
    dish: str  # the dish as it was written
    item_id: int | None  # the menu dish it matches, or None
    qty: int | None
    net: float | None
    problem: str | None


class UnmatchedDish(BaseModel):
    dish: str
    rows: int


class ImportPreview(BaseModel):
    draft_id: int
    filename: str
    kind: str
    read_by_ai: bool
    notes: str | None  # the AI's remarks about a PDF (blurry lines, a missing year, ...)
    rows_total: int
    rows_ok: int
    problems: int
    days: int
    date_from: date | None
    date_to: date | None
    new_days: int
    replaced_days: int
    dishes_sold: int
    net_sales_rm: float
    unmatched: list[UnmatchedDish]
    rows: list[DraftRow]  # the first rows to check; problems come first
    rows_shown: int


class RowEdit(BaseModel):
    i: int
    drop: bool = False
    date: str | None = None
    item_id: int | None = None
    qty: int | None = Field(default=None, ge=0, le=1_000_000)
    net: float | None = Field(default=None, ge=0, le=10_000_000)


class ConfirmIn(BaseModel):
    draft_id: int
    edits: list[RowEdit] = []
    dish_map: dict[str, int | None] = {}  # dish as written -> menu dish id (None = leave those rows out)


class ImportResult(BaseModel):
    import_id: int
    filename: str
    days: int
    rows_saved: int
    rows_left_out: int
    new_days: int
    replaced_days: int
    dishes_sold: int
    net_sales_rm: float
    date_from: date
    date_to: date
    today: date


class Coverage(BaseModel):
    first_date: date | None
    last_date: date | None
    days: int
    rows: int


class ImportOut(BaseModel):
    id: int
    ts: datetime
    filename: str
    kind: str
    read_by_ai: bool
    date_from: date
    date_to: date
    days: int
    rows: int
    status: str
    user_name: str | None


class RemovalOut(BaseModel):
    id: int
    ts: datetime
    label: str
    date_from: date
    date_to: date
    days: int
    rows: int
    user_name: str | None


class SalesOverview(BaseModel):
    coverage: Coverage
    today: date
    today_is_demo_date: bool
    imports: list[ImportOut]
    removed: list[RemovalOut]  # taken out, can still be restored
    ai_available: bool  # PDF files can be read


class RemoveIn(BaseModel):
    import_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None


class RemovePreview(BaseModel):
    label: str
    date_from: date
    date_to: date
    days: int
    rows: int
    today_now: date
    today_after: date | None  # where "today" moves to; None when a demo date is set (it stays)


class RemoveResult(BaseModel):
    removal: RemovalOut
    today: date
