"""Setup without any external sales-system prerequisite."""
import pytest
from sqlalchemy import func, inspect, select, text

from app.modules.activity.models import ActivityLog
from app.modules.calendar.models import CalendarEvent
from app.modules.sales.models import SalesDaily
from tests.conftest import as_user


def status(client, user):
    response = client.get("/api/setup/status", headers=as_user(user))
    assert response.status_code == 200
    return response.json()


def test_country_goes_directly_to_stock_and_setup_completes(client, users, db, loaded):
    owner = users["owner"]
    sales_before = db.scalar(select(func.count()).select_from(SalesDaily))
    assert status(client, owner)["step"] == "country"
    result = client.post("/api/setup/country", json={"country": "MY"}, headers=as_user(owner))
    assert result.status_code == 200
    assert result.json()["status"]["step"] == "inventory"
    assert result.json()["status"]["currency"] == "MYR"
    assert client.post("/api/setup/complete", json={}, headers=as_user(owner)).status_code == 409
    assert client.post("/api/inventory/onboarding/confirm", headers=as_user(owner)).status_code == 200
    assert status(client, owner)["step"] == "calendar"
    done = client.post("/api/setup/complete", json={"skip_calendar": True}, headers=as_user(owner))
    assert done.status_code == 200
    assert (done.json()["complete"], done.json()["step"], done.json()["calendar_skipped"]) == (True, "done", True)
    assert "pos_provider" not in done.json()
    assert "pos_connected_at" not in done.json()
    assert db.scalar(select(func.count()).select_from(SalesDaily)) == sales_before > 0
    actions = set(db.scalars(select(ActivityLog.action)))
    assert {"setup_country_chosen", "onboarding_confirmed", "setup_completed"} <= actions
    assert "pos_connected" not in actions
    assert client.get("/api/dashboard", headers=as_user(owner)).status_code == 200


def test_setup_requires_country_and_owner(client, users, loaded):
    owner = users["owner"]
    assert client.post("/api/setup/complete", json={}, headers=as_user(owner)).status_code == 409
    assert client.post("/api/setup/country", json={"country": "SG"}, headers=as_user(owner)).status_code == 422
    for role in ("manager", "staff"):
        headers = as_user(users[role])
        assert client.post("/api/setup/country", json={"country": "MY"}, headers=headers).status_code == 403
        assert client.post("/api/setup/complete", json={}, headers=headers).status_code == 403
    assert client.get("/api/setup/status").status_code == 401


def test_country_holidays_are_idempotent(client, users, db, loaded):
    headers = as_user(users["owner"])
    first = client.post("/api/setup/country", json={"country": "MY"}, headers=headers).json()
    count = db.scalar(select(func.count()).select_from(CalendarEvent))
    second = client.post("/api/setup/country", json={"country": "MY"}, headers=headers).json()
    assert first["holidays_added"] > 0
    assert second["holidays_added"] == 0
    assert db.scalar(select(func.count()).select_from(CalendarEvent)) == count


def test_existing_database_with_retired_connection_columns_still_works(client, users, db, loaded):
    owner = users["owner"]
    client.post("/api/setup/country", json={"country": "MY"}, headers=as_user(owner))
    db.execute(text("ALTER TABLE tenant_setup ADD COLUMN pos_provider VARCHAR(30)"))
    db.execute(text("ALTER TABLE tenant_setup ADD COLUMN pos_connected_at DATETIME"))
    db.execute(text("UPDATE tenant_setup SET pos_provider = 'feedme'"))
    db.commit()
    assert status(client, owner)["step"] == "inventory"
    assert client.post("/api/inventory/onboarding/confirm", headers=as_user(owner)).status_code == 200
    result = client.post("/api/setup/complete", json={"skip_calendar": True}, headers=as_user(owner))
    assert result.json()["complete"] is True
    assert db.scalar(text("SELECT pos_provider FROM tenant_setup")) == "feedme"


def test_new_database_and_api_schema_have_no_sales_connection_feature(client, db):
    assert not inspect(db.get_bind()).has_table("pos_imports")
    paths = client.get("/openapi.json").json()["paths"]
    assert not any(path.startswith("/api/pos") for path in paths)


@pytest.mark.parametrize(("method", "path"), [
    ("GET", "/api/pos/status"),
    ("POST", "/api/pos/connect"),
    ("POST", "/api/pos/import"),
    ("POST", "/api/pos/import/preview"),
    ("GET", "/api/pos/feedme/days"),
    ("GET", "/api/pos/feedme/preview"),
    ("GET", "/api/pos/feedme/export.csv"),
])
def test_removed_endpoints_are_not_available(client, users, method, path):
    response = client.request(method, path, headers=as_user(users["owner"]))
    # The SPA's GET-only fallback may report Method Not Allowed for removed POST routes.
    assert response.status_code in (404, 405)
