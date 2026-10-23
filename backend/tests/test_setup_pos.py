"""First-time setup wizard (country, POS, stock, calendar) and the simulated-FeedMe sales import."""
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.modules.activity.models import ActivityLog
from app.modules.calendar.models import CalendarEvent
from app.modules.planning import refresh
from app.modules.pos import feedme
from app.modules.sales.models import SalesDaily
from tests.conftest import as_user


@pytest.fixture()
def background(monkeypatch):
    calls = []
    monkeypatch.setattr(refresh, "run_recompute", lambda tenant_id, user_id, trigger: calls.append(trigger))
    return calls


def actions(db):
    return [a.action for a in db.scalars(select(ActivityLog).order_by(ActivityLog.id))]


def setup_status(client, user):
    return client.get("/api/setup/status", headers=as_user(user)).json()


def feedme_csv(client, user, start, end):
    r = client.get("/api/pos/feedme/export.csv", params={"date_from": start, "date_to": end}, headers=as_user(user))
    assert r.status_code == 200, r.text
    return r


# ---------- wizard ----------
def test_wizard_steps_in_order(client, users, db, loaded):
    owner = users["owner"]
    assert setup_status(client, owner)["step"] == "country"

    r = client.post("/api/setup/country", json={"country": "MY"}, headers=as_user(owner)).json()
    assert (r["status"]["currency"], r["status"]["country_name"], r["status"]["step"]) == ("MYR", "Malaysia", "pos")

    assert client.post("/api/pos/connect", json={"provider": "feedme"}, headers=as_user(owner)).status_code == 200
    assert setup_status(client, owner)["step"] == "inventory"

    # Finishing early is refused; confirming the stock moves the wizard to the optional calendar step.
    assert client.post("/api/setup/complete", json={}, headers=as_user(owner)).status_code == 409
    assert client.post("/api/inventory/onboarding/confirm", headers=as_user(owner)).status_code == 200
    assert setup_status(client, owner)["step"] == "calendar"

    done = client.post("/api/setup/complete", json={"skip_calendar": True}, headers=as_user(owner)).json()
    assert (done["complete"], done["calendar_skipped"], done["step"]) == (True, True, "done")
    assert {"setup_country_chosen", "pos_connected", "onboarding_confirmed", "setup_completed"} <= set(actions(db))


def test_only_malaysia_and_only_the_owner(client, users, loaded):
    assert client.post("/api/setup/country", json={"country": "SG"}, headers=as_user(users["owner"])).status_code == 422
    assert client.post("/api/setup/country", json={"country": "MY"}, headers=as_user(users["manager"])).status_code == 403
    assert client.post("/api/pos/connect", json={"provider": "feedme"}, headers=as_user(users["staff"])).status_code == 403
    assert client.post("/api/pos/connect", json={"provider": "loyverse"}, headers=as_user(users["owner"])).status_code == 422
    assert client.get("/api/setup/status").status_code == 401


def test_malaysian_holidays_are_added_once_without_duplicates(client, users, db, loaded):
    owner = users["owner"]
    before = db.scalar(select(func.count()).select_from(CalendarEvent).where(CalendarEvent.type == "public_holiday"))
    first = client.post("/api/setup/country", json={"country": "MY"}, headers=as_user(owner)).json()
    second = client.post("/api/setup/country", json={"country": "MY"}, headers=as_user(owner)).json()
    after = db.scalar(select(func.count()).select_from(CalendarEvent).where(CalendarEvent.type == "public_holiday"))
    assert first["holidays_added"] > 0 and first["holidays_already_there"] > 0  # the demo already has the 2026 dates
    assert (second["holidays_added"], after) == (0, before + first["holidays_added"])


# ---------- simulated FeedMe ----------
def test_feedme_export_matches_history_and_continues_it(users, loaded):
    history = feedme.last_history_date(settings.data_dir)
    old = feedme.export_rows(settings.data_dir, history, history)
    assert list(old.columns) == feedme.COLUMNS and len(old) > 50
    day_after = history + timedelta(days=1)
    new1 = feedme.export_rows(settings.data_dir, day_after, day_after)
    new2 = feedme.export_rows(settings.data_dir, day_after, day_after + timedelta(days=2))
    assert len(new1) > 50
    assert new1.equals(new2[new2.Date == new1.Date.iloc[0]].reset_index(drop=True))  # repeatable


def test_feedme_cannot_export_the_future(client, users, loaded):
    r = client.get("/api/pos/feedme/export.csv", params={"date_from": "2026-10-22", "date_to": "2026-10-30"}, headers=as_user(users["manager"]))
    assert r.status_code == 422 and "only has sales up to" in r.json()["detail"]
    assert client.get("/api/pos/feedme/days", headers=as_user(users["staff"])).status_code == 403


# ---------- import ----------
def import_body(text, name="export.csv"):
    return {"filename": name, "csv_text": text}


def connect(client, users):
    client.post("/api/pos/connect", json={"provider": "feedme"}, headers=as_user(users["owner"]))


def test_import_new_day_moves_today_and_is_logged(client, users, db, loaded, background):
    connect(client, users)
    manager = users["manager"]
    text = feedme_csv(client, manager, "2026-10-22", "2026-10-22").text
    assert client.get("/api/pos/status", headers=as_user(manager)).json()["next_to_import"] == "2026-10-22"

    preview = client.post("/api/pos/import/preview", json=import_body(text), headers=as_user(manager)).json()
    assert (preview["new_days"], preview["replaced_days"], preview["days"], preview["bad_count"]) == (1, 0, 1, 0)
    assert preview["unmatched"] == [] and preview["net_sales_rm"] > 0
    assert db.scalar(select(func.max(SalesDaily.date))).isoformat() == "2026-10-21"  # preview saves nothing

    done = client.post("/api/pos/import", json=import_body(text), headers=as_user(manager))
    assert done.status_code == 200
    assert db.scalar(select(func.max(SalesDaily.date))).isoformat() == "2026-10-22"
    status = client.get("/api/pos/status", headers=as_user(manager)).json()
    assert (status["today"], status["last_import"]["days"], status["last_import"]["user_name"]) == ("2026-10-23", 1, "Siti")
    assert "sales_imported" in actions(db) and background == []  # one new day does not re-measure buffers


def test_reimport_replaces_the_day_instead_of_doubling_it(client, users, db, loaded, background):
    connect(client, users)
    manager = users["manager"]
    text = feedme_csv(client, manager, "2026-10-20", "2026-10-21").text
    total_before = db.scalar(select(func.sum(SalesDaily.qty)))
    summary = client.post("/api/pos/import", json=import_body(text), headers=as_user(manager)).json()
    assert (summary["new_days"], summary["replaced_days"]) == (0, 2)
    assert db.scalar(select(func.sum(SalesDaily.qty))) == total_before


def test_import_reports_unknown_dishes_and_bad_rows_without_guessing(client, users, db, loaded):
    connect(client, users)
    text = (
        "Date,Item Code,Item Name,Qty Sold\n"
        "2026-10-22,M001,White rice,5\n"        # fine, matched by code
        "2026-10-22,,Telur Dadar,2\n"           # fine, matched by name
        "2026-10-22,X999,Dragon Burger,4\n"     # not on the menu
        "22/10/2026,M003,Telur Mata,x\n"        # bad quantity
        "2026-12-31,M001,White rice,1\n"        # after today
        "someday,M001,White rice,1\n"           # bad date
    )
    s = client.post("/api/pos/import/preview", json=import_body(text), headers=as_user(users["manager"])).json()
    assert s["rows_total"] == 6 and s["rows_ok"] == 2 and s["dishes_sold"] == 7
    assert s["unmatched"] == [{"name": "Dragon Burger", "rows": 1}] and s["bad_count"] == 3
    assert any("after today" in b["reason"] for b in s["bad_rows"])


def test_import_rules(client, users, db, loaded):
    manager, staff, owner = users["manager"], users["staff"], users["owner"]
    text = "Date,Item Code,Qty Sold\n2026-10-22,M001,5\n"
    assert client.post("/api/pos/import", json=import_body(text), headers=as_user(staff)).status_code == 403
    assert client.post("/api/pos/import", json=import_body(text), headers=as_user(manager)).status_code == 409  # not connected
    connect(client, users)
    assert client.post("/api/pos/import", json=import_body("Date,Qty Sold\n2026-10-22,5\n"), headers=as_user(manager)).status_code == 422
    assert client.post("/api/pos/import", json=import_body("Date,Item Code,Qty Sold\n2026-10-22,NOPE,5\n"), headers=as_user(manager)).status_code == 422
    assert client.post("/api/pos/import", json=import_body(text), headers=as_user(owner)).status_code == 200


def test_big_catch_up_asks_for_new_buffers(client, users, db, loaded, background):
    connect(client, users)
    # Seven new days would be in the future for the demo clock, so pin the demo date forward first.
    client.patch("/api/settings", json={"today_override": "2026-11-05"}, headers=as_user(users["owner"]))
    rows = ["Date,Item Code,Qty Sold"] + [f"2026-10-{d},M001,3" for d in range(22, 30)]
    r = client.post("/api/pos/import", json=import_body("\n".join(rows)), headers=as_user(users["manager"]))
    assert r.status_code == 200 and r.json()["new_days"] == 8
    assert background == ["sales_import"]
