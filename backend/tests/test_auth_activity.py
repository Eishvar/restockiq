from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.activity import log_action
from app.core.auth import require_role
from app.db import get_db
from app.modules.activity.models import ActivityLog
from tests.conftest import as_user


# ---------- /api/me and /api/users ----------
def test_users_lists_three_roles(client):
    r = client.get("/api/users")
    assert r.status_code == 200
    assert {u["role"] for u in r.json()} == {"owner", "manager", "staff"}


def test_me_follows_the_chosen_user(client, users):
    assert client.get("/api/me", headers=as_user(users["owner"])).json()["role"] == "owner"
    me = client.get("/api/me", headers=as_user(users["staff"])).json()
    assert me["role"] == "staff" and me["name"] == users["staff"].name


def test_me_without_or_with_unknown_user_is_401(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"X-User-Id": "9999"}).status_code == 401


# ---------- require_role ----------
def _app_with_owner_only_route(db):
    mini = FastAPI()
    mini.dependency_overrides[get_db] = lambda: db

    @mini.get("/owner-only")
    def owner_only(user=Depends(require_role("owner"))):
        return {"ok": user.role}

    @mini.get("/manager-up")
    def manager_up(user=Depends(require_role("manager"))):
        return {"ok": user.role}

    return TestClient(mini)


def test_require_role_hierarchy(db, users):
    c = _app_with_owner_only_route(db)
    assert c.get("/owner-only", headers=as_user(users["owner"])).status_code == 200
    assert c.get("/owner-only", headers=as_user(users["manager"])).status_code == 403
    assert c.get("/manager-up", headers=as_user(users["owner"])).status_code == 200  # owner > manager
    assert c.get("/manager-up", headers=as_user(users["manager"])).status_code == 200
    assert c.get("/manager-up", headers=as_user(users["staff"])).status_code == 403


def test_require_role_rejects_unknown_role_name():
    import pytest

    with pytest.raises(ValueError):
        require_role("admin")


# ---------- log_action ----------
def test_log_action_records_who_what_and_details(db, users):
    row = log_action(db, users["manager"], "plan_generated", "plan_run", 7, {"horizon_days": 3})
    db.commit()
    saved = db.get(ActivityLog, row.id)
    assert saved.user_id == users["manager"].id
    assert saved.role == "manager"
    assert saved.tenant_id == users["manager"].tenant_id
    assert saved.action == "plan_generated"
    assert (saved.entity_type, saved.entity_id) == ("plan_run", "7")
    assert saved.details == {"horizon_days": 3}
    assert saved.ts is not None


def test_log_action_system_action_needs_tenant(db, users):
    row = log_action(db, None, "nightly_job", tenant_id=users["owner"].tenant_id)
    assert row.user_id is None and row.role is None
    try:
        log_action(db, None, "nightly_job")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


# ---------- /api/activity ----------
def test_activity_is_forbidden_for_staff(client, users):
    assert client.get("/api/activity", headers=as_user(users["staff"])).status_code == 403


def test_activity_newest_first_for_manager_and_owner(client, db, users):
    log_action(db, users["staff"], "inventory_edit", "inventory", 1)
    log_action(db, users["manager"], "plan_generated", "plan_run", 2)
    db.commit()
    for role in ("manager", "owner"):
        r = client.get("/api/activity", headers=as_user(users[role]))
        assert r.status_code == 200
        rows = r.json()
        assert [x["action"] for x in rows] == ["plan_generated", "inventory_edit"]
        assert rows[0]["user_name"] == users["manager"].name
        assert rows[1]["role"] == "staff"


def test_activity_pagination(client, db, users):
    for i in range(5):
        log_action(db, users["owner"], f"a{i}")
    db.commit()
    r = client.get("/api/activity?limit=2&offset=1", headers=as_user(users["owner"]))
    assert [x["action"] for x in r.json()] == ["a3", "a2"]
