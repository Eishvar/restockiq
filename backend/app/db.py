"""Database engine, session factory and table creation (SQLite locally, PostgreSQL on Replit)."""
from collections.abc import Iterator
from importlib import import_module

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# Every module that owns tables. Importing its models registers them on Base.metadata.
MODEL_MODULES = [
    "settings",  # tenants, users
    "catalog",  # menu_items, suppliers, ingredients, recipes
    "sales",  # sales_daily
    "inventory",  # inventory_items, inventory_movements
    "calendar",  # calendar_events
    "planning",  # safety_profiles, forecast_quality, plan_runs, forecast_lines, purchase_orders, po_lines
    "assistant",  # ai_suggestions
    "activity",  # activity_log
]


class Base(DeclarativeBase):
    pass


def _normalise_url(url: str) -> str:
    # Some hosts hand out "postgres://", which SQLAlchemy 2.0 no longer accepts.
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


_url = _normalise_url(settings.database_url)
engine = create_engine(
    _url,
    connect_args={"check_same_thread": False} if _url.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def import_all_models() -> None:
    for name in MODEL_MODULES:
        import_module(f"app.modules.{name}.models")


def init_db(bind=None) -> None:
    """Create any missing tables (never alters existing ones)."""
    import_all_models()
    Base.metadata.create_all(bind or engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
