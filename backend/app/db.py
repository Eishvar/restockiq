"""Database engine, session factory and table creation (SQLite locally, PostgreSQL on Replit)."""
from collections.abc import Iterator
from importlib import import_module

from sqlalchemy import create_engine, inspect, text
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
    "setup",  # tenant_setup (first-time wizard progress)
]


class Base(DeclarativeBase):
    pass


def _normalise_url(url: str) -> str:
    """Make a host-provided database URL point at the driver we install (psycopg2).

    Hosts hand out "postgres://" or "postgresql://". SQLAlchemy 2.0 rejects the first, and 2.1 picks the
    newer `psycopg` driver for the second, which is not installed, so name psycopg2 explicitly.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix) :]
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


# Columns added after the first release. create_all() never alters an existing table, so a database made before
# these existed (such as the live one) gets them added here. Each entry: (table, column, SQL type and default).
ADDED_COLUMNS = [
    ("suppliers", "active", {"postgresql": "BOOLEAN NOT NULL DEFAULT TRUE", "default": "BOOLEAN NOT NULL DEFAULT 1"}),
]


def _add_missing_columns(bind) -> None:
    inspector = inspect(bind)
    for table, column, ddl in ADDED_COLUMNS:
        if not inspector.has_table(table) or column in {c["name"] for c in inspector.get_columns(table)}:
            continue
        with bind.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl.get(bind.dialect.name, ddl['default'])}"))


def init_db(bind=None) -> None:
    """Create any missing tables and the few columns added since the first release."""
    import_all_models()
    bind = bind or engine
    Base.metadata.create_all(bind)
    _add_missing_columns(bind)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
