"""Owner settings and the business calendar: roles, validation, logging, and the safety-buffer refresh."""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.modules.activity.models import ActivityLog
from app.modules.calendar import service as calendar_service
from app.modules.calendar.models import CalendarEvent
from app.modules.catalog.models import Supplier
from app.modules.planning import refresh
from app.modules.settings import service as settings_service
from app.modules.settings.models import Tenant
from tests.conftest import as_user


@pytest.fixture()
def recomputes(monkeypatch):
    """Replace the (slow) safety recompute with a recorder, everywhere it is called."""
    calls = []

    def fake(db, tenant):
        calls.append(tenant.risk_profile)
        return {"origins": 80, "profiles": 518, "seconds": 0.1}

    monkeypatch.setattr(settings_service, "recompute_safety", fake)
    monkeypatch.setattr(calendar_service, "recompute_safety", fake)
    monkeypatch.setattr(refresh, "recompute_safety", fake)
    return calls


@pytest.fixture()
def background(monkeypatch):
    """Record the background refresh requests the calendar endpoints make."""
    calls = []
    monkeypatch.setattr(refresh, "run_recompute", lambda tenant_id, user_id, trigger: calls.append((tenant_id, user_id, trigger)))
    return calls


def patch_settings(client, user, **body):
    return client.patch("/api/settings", json=body, headers=as_user(user))


def actions(db):
    return [a.action for a in db.scalars(select(ActivityLog).order_by(ActivityLog.id))]


# ---------- settings ----------
def test_settings_are_owner_only(client, users, loaded):
    assert client.get("/api/settings", headers=as_user(users["manager"])).status_code == 403
    assert client.get("/api/settings", headers=as_user(users["staff"])).status_code == 403
    assert patch_settings(client, users["manager"], manual_planning_hours=8).status_code == 403
    assert client.get("/api/settings").status_code == 401


def test_settings_show_everything_the_page_needs(client, users, loaded):
    s = client.get("/api/settings", headers=as_user(users["owner"])).json()
    assert (s["risk_profile"], s["manual_planning_hours"], s["today_override"], s["today"]) == ("balanced", 16, None, "2026-10-22")
    assert s["service_levels"] == {"lean": [0.7, 0.8, 0.9], "balanced": [0.8, 0.9, 0.95], "never_run_out": [0.9, 0.95, 0.98]}
    assert {x["name"] for x in s["suppliers"]} >= {"Utara Frozen Supply"} and all(x["whatsapp"] for x in s["suppliers"])


def test_changing_the_risk_profile_recomputes_buffers_and_logs_before_after(client, db, users, loaded, recomputes):
    r = patch_settings(client, users["owner"], risk_profile="never_run_out")
    assert r.status_code == 200 and r.json()["risk_profile"] == "never_run_out"
    assert recomputes == ["never_run_out"]  # measured again with the new profile
    assert db.scalars(select(Tenant)).one().risk_profile == "never_run_out"
    assert actions(db) == ["settings_changed", "safety_recomputed"]
    log = db.scalars(select(ActivityLog).where(ActivityLog.action == "settings_changed")).one()
    assert log.role == "owner" and log.details["before"]["risk_profile"] == "balanced" and log.details["after"]["risk_profile"] == "never_run_out"
    assert db.scalars(select(ActivityLog).where(ActivityLog.action == "safety_recomputed")).one().details["trigger"] == "risk_profile"


def test_other_settings_do_not_recompute_and_unchanged_values_are_not_logged(client, db, users, loaded, recomputes):
    assert patch_settings(client, users["owner"], manual_planning_hours=12.5).json()["manual_planning_hours"] == 12.5
    assert recomputes == [] and actions(db) == ["settings_changed"]
    patch_settings(client, users["owner"], manual_planning_hours=12.5, risk_profile="balanced")
    assert actions(db) == ["settings_changed"]  # nothing changed the second time


@pytest.mark.parametrize("body", [{"risk_profile": "reckless"}, {"manual_planning_hours": 0}, {"manual_planning_hours": 500},
                                  {"today_override": "not-a-date"}])
def test_settings_validation(client, users, loaded, recomputes, body):
    assert patch_settings(client, users["owner"], **body).status_code == 422


def test_today_override_drives_the_app_and_can_be_cleared(client, db, users, loaded):
    owner, manager = users["owner"], users["manager"]
    assert patch_settings(client, owner, today_override="2026-10-20").json()["today"] == "2026-10-20"
    plan = client.post("/api/planning/plans", json={"horizon_days": 2}, headers=as_user(manager)).json()
    assert plan["today"] == "2026-10-20"  # plans use the override
    assert client.get("/api/planning/context", headers=as_user(manager)).json()["today"] == "2026-10-20"
    cleared = patch_settings(client, owner, today_override=None).json()
    assert cleared["today_override"] is None and cleared["today"] == "2026-10-22"


def test_today_override_beats_the_env_variable(client, users, loaded, monkeypatch):
    from app.config import settings as cfg
    from dataclasses import replace
    monkeypatch.setattr("app.core.today.settings", replace(cfg, today="2026-10-25"))
    assert client.get("/api/settings", headers=as_user(users["owner"])).json()["today"] == "2026-10-25"
    assert patch_settings(client, users["owner"], today_override="2026-10-21").json()["today"] == "2026-10-21"


def test_supplier_contact_and_minimum_order_can_be_edited_by_the_owner(client, db, users, loaded):
    sup = db.scalars(select(Supplier).order_by(Supplier.id)).first()
    url = f"/api/settings/suppliers/{sup.id}"
    assert client.patch(url, json={"min_order_rm": 10}, headers=as_user(users["manager"])).status_code == 403
    r = client.patch(url, json={"whatsapp": "+60 12-345 6789", "min_order_rm": 80}, headers=as_user(users["owner"]))
    assert r.status_code == 200 and r.json()["whatsapp"] == "+60 12-345 6789" and r.json()["min_order_rm"] == 80
    log = db.scalars(select(ActivityLog).where(ActivityLog.action == "supplier_updated")).one()
    assert log.details["after"]["min_order_rm"] == 80 and log.details["before"]["min_order_rm"] != 80
    assert log.details["after"]["whatsapp"] == "+60 12-345 6789"
    for bad in ({"whatsapp": "call me"}, {"min_order_rm": -1}, {"name": ""}):
        assert client.patch(url, json=bad, headers=as_user(users["owner"])).status_code == 422
    assert client.patch("/api/settings/suppliers/9999", json={"min_order_rm": 1}, headers=as_user(users["owner"])).status_code == 404


def test_edited_whatsapp_number_is_used_in_the_order_link(client, db, users, loaded):
    sup = db.scalars(select(Supplier).order_by(Supplier.id)).first()
    client.patch(f"/api/settings/suppliers/{sup.id}", json={"whatsapp": "+60 19-888 7777"}, headers=as_user(users["owner"]))
    plan = client.post("/api/planning/plans", json={"horizon_days": 3}, headers=as_user(users["manager"])).json()
    order = next(o for o in plan["orders"] if o["supplier_id"] == sup.id)
    for step, who in (("submit", "manager"), ("approve", "owner")):
        client.post(f"/api/planning/orders/{order['id']}/{step}", headers=as_user(users[who]))
    sent = client.post(f"/api/planning/orders/{order['id']}/send", headers=as_user(users["owner"])).json()
    assert sent["whatsapp_url"].startswith("https://wa.me/60198887777?text=")


# ---------- calendar ----------
HOLIDAY = {"type": "public_holiday", "name": "Deepavali", "start_date": "2026-11-08", "end_date": "2026-11-08"}
PERIOD = {"type": "period", "label": "School Holidays", "name": "Year-end school holidays",
          "start_date": "2026-11-14", "end_date": "2026-12-31"}


def test_calendar_needs_manager(client, users, loaded):
    assert client.get("/api/calendar", headers=as_user(users["staff"])).status_code == 403
    assert client.post("/api/calendar", json=HOLIDAY, headers=as_user(users["staff"])).status_code == 403
    assert client.get("/api/calendar", headers=as_user(users["manager"])).status_code == 200


def test_list_shows_events_labels_and_freshness(client, users, loaded):
    c = client.get("/api/calendar", headers=as_user(users["owner"])).json()
    assert len(c["events"]) == 29 and {"semester", "break", "intake"} <= set(c["labels"]) and c["today"] == "2026-10-22"
    starts = [e["start_date"] for e in c["events"]]
    assert starts == sorted(starts, reverse=True)  # newest first
    assert c["buffers_updated_at"] is None  # the test database has no computed buffers yet


def test_add_edit_delete_are_logged_and_each_schedules_a_background_refresh(client, db, users, loaded, background):
    h = as_user(users["manager"])
    added = client.post("/api/calendar", json=PERIOD, headers=h)
    assert added.status_code == 201
    e = added.json()
    assert e["label"] == "school_holidays" and e["source"] == "manual" and e["status"] == "approved"  # label normalised

    edited = client.patch(f"/api/calendar/{e['id']}", json={"end_date": "2027-01-03", "name": "School holidays"}, headers=h)
    assert edited.status_code == 200 and edited.json()["end_date"] == "2027-01-03"
    assert client.delete(f"/api/calendar/{e['id']}", headers=h).status_code == 204
    assert db.get(CalendarEvent, e["id"]) is None

    assert background == [(1, users["manager"].id, "calendar")] * 3  # buffers are refreshed after each change
    assert actions(db) == ["calendar_event_added", "calendar_event_edited", "calendar_event_deleted"]
    edit_log = db.scalars(select(ActivityLog).where(ActivityLog.action == "calendar_event_edited")).one()
    assert edit_log.details["before"]["end_date"] == "2026-12-31" and edit_log.details["after"]["end_date"] == "2027-01-03"
    assert edit_log.role == "manager"


@pytest.mark.parametrize("body", [
    {**HOLIDAY, "end_date": "2026-11-01"},  # ends before it starts
    {**PERIOD, "label": None},  # a period needs a label
    {**PERIOD, "label": "   "},
    {**HOLIDAY, "type": "birthday"},
    {**HOLIDAY, "name": ""},
])
def test_calendar_validation(client, users, loaded, background, body):
    assert client.post("/api/calendar", json=body, headers=as_user(users["manager"])).status_code == 422
    assert background == []


def test_holidays_and_events_drop_any_label(client, users, loaded, background):
    r = client.post("/api/calendar", json={**HOLIDAY, "label": "ignored"}, headers=as_user(users["manager"]))
    assert r.json()["label"] is None


def test_edit_cannot_break_an_entry(client, users, loaded, background):
    h = as_user(users["manager"])
    e = client.post("/api/calendar", json=PERIOD, headers=h).json()
    assert client.patch(f"/api/calendar/{e['id']}", json={"end_date": "2026-01-01"}, headers=h).status_code == 422
    assert client.patch(f"/api/calendar/{e['id']}", json={"label": None}, headers=h).status_code == 422
    still = next(x for x in client.get("/api/calendar", headers=h).json()["events"] if x["id"] == e["id"])
    assert still["end_date"] == "2026-12-31" and still["label"] == "school_holidays"
    # turning it into a holiday clears the label
    r = client.patch(f"/api/calendar/{e['id']}", json={"type": "public_holiday", "end_date": "2026-11-14"}, headers=h)
    assert r.status_code == 200 and r.json()["label"] is None
    assert client.patch("/api/calendar/9999", json={"name": "x"}, headers=h).status_code == 404
    assert client.delete("/api/calendar/9999", headers=h).status_code == 404


def test_recompute_button_runs_now_and_is_logged(client, db, users, loaded, recomputes):
    assert client.post("/api/calendar/recompute", headers=as_user(users["staff"])).status_code == 403
    r = client.post("/api/calendar/recompute", headers=as_user(users["manager"]))
    assert r.status_code == 200 and r.json()["profiles"] == 518 and recomputes == ["balanced"]
    log = db.scalars(select(ActivityLog).where(ActivityLog.action == "safety_recomputed")).one()
    assert log.details["trigger"] == "manual" and log.role == "manager"


def test_a_calendar_change_changes_the_next_forecast(client, users, loaded, background):
    h = as_user(users["manager"])
    before = client.post("/api/planning/plans", json={"horizon_days": 3}, headers=h).json()["forecast"]["days"]
    client.post("/api/calendar", json={"type": "period", "label": "peak_season", "name": "Peak season",
                                       "start_date": "2026-10-23", "end_date": "2026-12-31"}, headers=h)
    after = client.post("/api/planning/plans", json={"horizon_days": 3}, headers=h).json()["forecast"]["days"]
    assert before[1]["drivers"]["state"] != after[1]["drivers"]["state"]
    assert "peak_season" in after[1]["drivers"]["state"]
    assert abs(after[1]["total"] - before[1]["total"]) > 1


def test_background_refresh_recomputes_and_logs_in_its_own_session(db, users, loaded, monkeypatch):
    engine = db.get_bind()
    monkeypatch.setattr(refresh, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    seen = []
    monkeypatch.setattr(refresh, "recompute_safety", lambda session, tenant: seen.append(tenant.id) or {"origins": 3})
    refresh.run_recompute(1, users["manager"].id, "calendar")
    assert seen == [1]
    log = db.scalars(select(ActivityLog).where(ActivityLog.action == "safety_recomputed")).one()
    assert log.details == {"trigger": "calendar", "origins": 3} and log.role == "manager"


def test_background_refresh_never_raises(db, users, loaded, monkeypatch):
    monkeypatch.setattr(refresh, "SessionLocal", sessionmaker(bind=db.get_bind(), expire_on_commit=False))

    def boom(session, tenant):
        raise RuntimeError("database went away")

    monkeypatch.setattr(refresh, "recompute_safety", boom)
    refresh.run_recompute(1, users["manager"].id, "calendar")  # must not raise
    assert db.scalars(select(ActivityLog).where(ActivityLog.action == "safety_recomputed")).first() is None


def test_reset_clears_the_demo_date_override(client, db, users, loaded, recomputes):
    patch_settings(client, users["owner"], today_override="2026-10-20")
    from app.seed.load import reset_demo_data
    reset_demo_data(db, compute_safety=False)
    assert client.get("/api/settings", headers=as_user(users["owner"])).json()["today_override"] is None
