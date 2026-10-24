"""Uploaded sales files, their previews, and the sales the owner has taken out (so they can be put back)."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SalesImport(Base):
    """One uploaded sales file that was saved. Its rows in sales_daily carry this id."""

    __tablename__ = "sales_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    filename: Mapped[str] = mapped_column(String(200), default="")
    kind: Mapped[str] = mapped_column(String(10), default="csv")  # csv | xlsx | pdf
    read_by_ai: Mapped[bool] = mapped_column(Boolean, default=False)  # a PDF is read by AI, so a person checked it
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    days: Mapped[int] = mapped_column(Integer)
    rows: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="active")  # active | removed
    skipped: Mapped[dict | None] = mapped_column(JSON, default=None)  # dishes not on the menu, rows left out


class SalesRemoval(Base):
    """Sales taken out of the app. While `restored_at` and `purged_at` are empty they can be put back."""

    __tablename__ = "sales_removals"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    label: Mapped[str] = mapped_column(String(200))  # "File sales.csv", "Days 1 Oct to 5 Oct", "Replaced by sales.csv"
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    days: Mapped[int] = mapped_column(Integer)
    rows: Mapped[int] = mapped_column(Integer)
    import_id: Mapped[int | None] = mapped_column(Integer, default=None)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)  # "deleted forever"


class SalesDailyRemoved(Base):
    """The rows of a removal, kept in their own table so every screen that reads sales_daily never sees them."""

    __tablename__ = "sales_daily_removed"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    removal_id: Mapped[int] = mapped_column(ForeignKey("sales_removals.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"))
    qty: Mapped[int] = mapped_column(Integer)
    net_sales_rm: Mapped[float] = mapped_column(Float)
    import_id: Mapped[int | None] = mapped_column(Integer, default=None)


class SalesDraft(Base):
    """A file that has been read and previewed but not saved yet (a person still has to check and confirm it)."""

    __tablename__ = "sales_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    ts: Mapped[datetime] = mapped_column(DateTime)
    filename: Mapped[str] = mapped_column(String(200), default="")
    kind: Mapped[str] = mapped_column(String(10), default="csv")
    read_by_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    rows: Mapped[list] = mapped_column(JSON)  # resolved rows, see service._resolve
