import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db, init_db
from app.main import app
from app.modules.settings.models import User
from app.seed.demo import ensure_demo_tenant


@pytest.fixture()
def db():
    """Fresh in-memory SQLite database with the demo tenant and users."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    ensure_demo_tenant(session)
    yield session
    session.close()


@pytest.fixture()
def users(db):
    """{'owner': User, 'manager': User, 'staff': User}"""
    return {u.role: u for u in db.scalars(select(User))}


@pytest.fixture()
def loaded(db):
    """Demo data (catalog, sales, inventory) loaded; returns the row counts."""
    from app.seed.load import load_demo_data

    return load_demo_data(db)


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)  # no `with`: skips the startup hook that would touch the real database
    app.dependency_overrides.clear()


def as_user(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}
