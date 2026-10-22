from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    # period | public_holiday | local_event
    type: Mapped[str] = mapped_column(String(20))
    # What the forecaster learns per (e.g. semester / break / intake); only used by periods.
    label: Mapped[str | None] = mapped_column(String(60), default=None)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default="approved")  # approved | suggested
    source: Mapped[str] = mapped_column(String(20), default="seed")  # seed | manual | ai
