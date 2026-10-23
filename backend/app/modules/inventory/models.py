from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
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


class InventoryBatch(Base):
    """One purchase of one ingredient: the same item bought on different days is tracked as separate batches.

    Each batch has its own procurement date, shelf life and price, so its expiry date is exact:
    expires_on = procured_on + shelf_life_days (computed, not stored). `InventoryItem.qty_base` and
    `InventoryItem.last_purchased_on` are totals kept in step with the batches by `service._sync`.
    """

    __tablename__ = "inventory_batches"
    __table_args__ = (UniqueConstraint("tenant_id", "ingredient_id", "procured_on"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), index=True)
    qty_base: Mapped[float] = mapped_column(Float)
    procured_on: Mapped[date] = mapped_column(Date)
    shelf_life_days: Mapped[int] = mapped_column(Integer)
    pack_price_rm: Mapped[float] = mapped_column(Float)  # price per pack paid for this batch
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
