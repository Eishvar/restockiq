from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PosImport(Base):
    """One uploaded sales file (the history shown on the dashboard's POS card)."""

    __tablename__ = "pos_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    provider: Mapped[str] = mapped_column(String(30))
    filename: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(20), default="manual_upload")  # manual_upload now; "auto_sync" later
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    days: Mapped[int] = mapped_column(Integer)
    rows: Mapped[int] = mapped_column(Integer)
    skipped: Mapped[dict | None] = mapped_column(JSON, default=None)  # dishes not on the menu, bad rows
