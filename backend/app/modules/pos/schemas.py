from datetime import date, datetime

from pydantic import BaseModel


class ConnectIn(BaseModel):
    provider: str


class ImportIn(BaseModel):
    filename: str = ""
    csv_text: str


class Unmatched(BaseModel):
    name: str
    rows: int


class BadRow(BaseModel):
    line: int
    reason: str


class ImportSummary(BaseModel):
    """What a file contains and what importing it would do (also returned after the import)."""

    rows_total: int
    rows_ok: int
    days: int
    date_from: date | None
    date_to: date | None
    new_days: int  # days the app has no sales for yet
    replaced_days: int  # days that already have sales; the file's version replaces them
    dishes_sold: int
    net_sales_rm: float
    unmatched: list[Unmatched]  # dishes in the file that are not on the menu; they are left out
    bad_count: int
    bad_rows: list[BadRow]  # first few only


class LastImport(BaseModel):
    ts: datetime
    filename: str
    date_from: date
    date_to: date
    days: int
    rows: int
    user_name: str | None


class PosStatus(BaseModel):
    provider: str | None
    connected_at: datetime | None
    latest_sales_date: date | None
    today: date
    next_to_import: date | None  # first day after the latest sales, if the POS has it ready
    last_import: LastImport | None


class FeedMeDay(BaseModel):
    date: date
    dishes: int
    net_sales_rm: float
    imported: bool


class FeedMePreview(BaseModel):
    columns: list[str]
    rows: list[list[str]]
    total_rows: int
    date_from: date
    date_to: date
