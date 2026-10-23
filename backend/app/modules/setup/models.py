from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TenantSetup(Base):
    """Where a business is in the first-time setup wizard. One row per tenant, created on first use.

    A separate table (not columns on `tenants`) so databases that already exist pick it up without a migration.
    """

    __tablename__ = "tenant_setup"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    country: Mapped[str | None] = mapped_column(String(2), default=None)  # ISO code, "MY" for now
    currency: Mapped[str | None] = mapped_column(String(3), default=None)  # ISO 4217, "MYR"
    pos_provider: Mapped[str | None] = mapped_column(String(30), default=None)  # "feedme"
    pos_connected_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    calendar_skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    setup_done_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
