from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# `code` is the business identifier from the source files (e.g. "M001", "CHICKEN_BREAST", "SUP-FRZ").
# It is only unique within a tenant, so every table also has an integer primary key.


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80))
    price_rm: Mapped[float] = mapped_column(Float)
    launch_date: Mapped[date | None] = mapped_column(Date, default=None)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(120), default="")
    delivery_days: Mapped[str] = mapped_column(String(60), default="Daily")
    lead_time_days: Mapped[int] = mapped_column(Integer, default=0)
    min_order_rm: Mapped[float] = mapped_column(Float, default=0)
    whatsapp: Mapped[str] = mapped_column(String(30), default="")


class Ingredient(Base):
    __tablename__ = "ingredients"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    code: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(160))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), default=None)
    storage: Mapped[str] = mapped_column(String(20), default="dry")  # freezer | chiller | dry | ...
    base_uom: Mapped[str] = mapped_column(String(10))  # g | ml | pcs
    pack_uom: Mapped[str] = mapped_column(String(60))  # e.g. "CTN (6x2kg)"
    pack_size_base: Mapped[float] = mapped_column(Float)
    pack_price_rm: Mapped[float] = mapped_column(Float)
    shelf_life_days: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), index=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), index=True)
    qty_per_serving: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="approved")
    source: Mapped[str] = mapped_column(String(20), default="seed")  # seed | manual | ai
