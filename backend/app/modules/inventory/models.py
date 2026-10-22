from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class InventoryItem(Base):
    """Current stock of one ingredient. Expiry = last_purchased_on + shelf_life_days (computed, not stored)."""

    __tablename__ = "inventory_items"
    __table_args__ = (UniqueConstraint("tenant_id", "ingredient_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"))
    qty_base: Mapped[float] = mapped_column(Float, default=0)
    last_purchased_on: Mapped[date | None] = mapped_column(Date, default=None)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    change_base: Mapped[float] = mapped_column(Float)
    # onboarding | adjust | received | discard_expired | removed
    reason: Mapped[str] = mapped_column(String(30))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    note: Mapped[str] = mapped_column(String(300), default="")
