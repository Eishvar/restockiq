from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(40), default="Asia/Kuala_Lumpur")
    # lean | balanced | never_run_out
    risk_profile: Mapped[str] = mapped_column(String(20), default="balanced")
    manual_planning_hours: Mapped[float] = mapped_column(Float, default=16)
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    # Demo override of "today" (Settings). Wins over the TODAY env var and the sales-derived date.
    today_override: Mapped[date | None] = mapped_column(Date, default=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    # owner | manager | staff
    role: Mapped[str] = mapped_column(String(20))
