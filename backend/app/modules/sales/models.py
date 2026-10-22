from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SalesDaily(Base):
    """One row per dish per day it sold (a missing row means 0 sold)."""

    __tablename__ = "sales_daily"
    __table_args__ = (UniqueConstraint("tenant_id", "date", "menu_item_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"))
    qty: Mapped[int] = mapped_column(Integer)
    net_sales_rm: Mapped[float] = mapped_column(Float)
