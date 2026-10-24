"""Sales data: upload (CSV, Excel, PDF read by AI), check and fix in a preview, remove and restore, stale plans."""
import io
from datetime import date, datetime

import pytest
from openpyxl import Workbook
from sqlalchemy import func, select

from app.ai import llm
from app.modules.activity.models import ActivityLog
from app.modules.catalog.models import MenuItem
from app.modules.planning import refresh
from app.modules.sales.models import SalesDaily
from app.modules.sales_data.models import SalesDailyRemoved
from app.modules.setup.models import TenantSetup
from tests.conftest import as_user
from tests.test_planning import act, make_plan

HEADER = "Date,Item Code,Item Name,Qty Sold,Net Sales (RM)"


@pytest.fixture()
def background(monkeypatch):
    calls = []
    monkeypatch.setattr(refresh, "run_recompute", lambda tenant_id, user_id, trigger: calls.append(trigger))
    return calls


def dish(db, name):
    return db.scalar(select(MenuItem).where(MenuItem.name == name))


def actions(db):
    return [a.action for a in db.scalars(select(ActivityLog).order_by(ActivityLog.id))]


def sales_count(db, day=None):
    stmt = select(func.count()).select_from(SalesDaily)
    if day:
        stmt = stmt.where(SalesDaily.date == day)
    return db.scalar(stmt)


def preview(client, user, name, data, content_type="text/csv"):
    return client.post("/api/sales/import/preview", files={"file": (name, data, content_type)}, headers=as_user(user))


def confirm(client, user, draft_id, **body):
    return client.post("/api/sales/import/confirm", json={"draft_id": draft_id, **body}, headers=as_user(user))


def csv_file(*lines, header=HEADER):
    return ("\n".join([header, *lines]) + "\n").encode()


def import_csv(client, user, *lines, name="sales.csv"):
    p = preview(client, user, name, csv_file(*lines)).json()
    return confirm(client, user, p["draft_id"]).json()


# ---------- CSV ----------
def test_csv_preview_saves_nothing_until_a_person_confirms(client, db, users, loaded, background):
    before = sales_count(db)
    data = csv_file("2026-10-22,,White rice,40,48.00", "2026-10-22,,Telur Dadar,25,", "2026-10-22,,Mystery Dish,3,9",
                    "not a date,,White rice,5,6", "2026-10-22,,White rice,-4,1")
    r = preview(client, users["manager"], "sales.csv", data)
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["kind"], p["read_by_ai"], p["rows_total"], p["rows_ok"], p["problems"]) == ("csv", False, 5, 2, 3)
    assert [(u["dish"], u["rows"]) for u in p["unmatched"]] == [("Mystery Dish", 1)]
    assert (p["days"], p["new_days"], p["replaced_days"], p["dishes_sold"]) == (1, 1, 0, 65)
    assert p["rows"][0]["problem"]  # rows that need a look come first
    assert sales_count(db) == before and "sales_imported" not in actions(db)  # a preview saves nothing

    c = confirm(client, users["manager"], p["draft_id"])
    assert c.status_code == 200, c.text
    done = c.json()
    assert (done["rows_saved"], done["rows_left_out"], done["new_days"], done["today"]) == (2, 3, 1, "2026-10-23")
    assert sales_count(db) == before + 2
    rice = db.scalar(select(SalesDaily).where(SalesDaily.date == date(2026, 10, 22), SalesDaily.menu_item_id == dish(db, "White rice").id))
    assert (rice.qty, rice.net_sales_rm, rice.import_id) == (40, 48.0, done["import_id"])
    egg = db.scalar(select(SalesDaily).where(SalesDaily.date == date(2026, 10, 22), SalesDaily.menu_item_id == dish(db, "Telur Dadar").id))
    assert egg.net_sales_rm == 37.5  # no amount in the file: quantity x menu price
    assert "sales_imported" in actions(db) and db.get(TenantSetup, 1).sales_changed_at is not None
    assert confirm(client, users["manager"], p["draft_id"]).status_code == 404  # the draft is used up
    assert background == []  # one new day is too few to re-measure the buffers


def test_header_row_does_not_have_to_be_first_and_semicolons_work(client, users, loaded):
    data = b"Sales report;;;\nPrinted by the till;;;\n\nDate;Item Name;Qty;Amount\n22/10/2026;White rice;7;8.40\n"
    p = preview(client, users["manager"], "till.csv", data).json()
    assert (p["rows_total"], p["rows_ok"], p["date_from"]) == (1, 1, "2026-10-22")  # DD/MM/YYYY is day first
    assert p["rows"][0]["net"] == 8.4


def test_wrong_files_are_refused_with_plain_reasons(client, users, loaded):
    h = users["manager"]
    r = preview(client, h, "old.xls", b"x")
    assert r.status_code == 422 and ".xlsx" in r.json()["detail"]
    assert preview(client, h, "notes.docx", b"x").status_code == 422
    r = preview(client, h, "sales.csv", b"Fruit,Count\napple,3\n")
    assert r.status_code == 422 and "Date" in r.json()["detail"] and "Fruit" in r.json()["detail"]
    assert preview(client, h, "sales.csv", (HEADER + "\n").encode()).status_code == 422  # header but no rows
    assert preview(client, h, "sales.xlsx", b"this is not a zip file").status_code == 422


# ---------- Excel ----------
def xlsx_file(sheets):
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets:
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_excel_with_a_title_dates_as_dates_and_numbers_as_numbers(client, db, users, loaded):
    data = xlsx_file([
        ("Read me", [["This sheet has no table"]]),
        ("Sales", [["Weekly sales"], [], ["Date", "Item Name", "Qty Sold", "Net Sales (RM)"],
                   [datetime(2026, 10, 22), "White rice", 12.0, 14.4], [datetime(2026, 10, 22), "Telur Dadar", 5, None]]),
    ])
    p = preview(client, users["manager"], "week.xlsx", data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet").json()
    assert (p["kind"], p["rows_ok"], p["date_from"], p["dishes_sold"]) == ("xlsx", 2, "2026-10-22", 17)
    assert confirm(client, users["manager"], p["draft_id"]).status_code == 200
    rice = db.scalar(select(SalesDaily).where(SalesDaily.date == date(2026, 10, 22), SalesDaily.menu_item_id == dish(db, "White rice").id))
    assert (rice.qty, rice.net_sales_rm) == (12, 14.4)


# ---------- fixing rows in the preview ----------
def test_a_person_can_map_a_dish_fix_a_number_and_leave_a_row_out(client, db, users, loaded):
    rice, egg = dish(db, "White rice"), dish(db, "Telur Dadar")
    p = preview(client, users["manager"], "typos.csv",
                csv_file("2026-10-22,,Whte rice,10,", "2026-10-22,,Telur Dadar,99,", "2026-10-22,,Telur Dadar,1,", "2026-10-22,,Whte rice,2,")).json()
    assert p["rows_ok"] == 2 and [u["dish"] for u in p["unmatched"]] == ["Whte rice"]
    by_line = {r["line"]: r for r in p["rows"]}
    edits = [{"i": by_line[3]["i"], "qty": 9}, {"i": by_line[4]["i"], "drop": True}]  # 99 was a typo for 9; drop the stray 1
    done = confirm(client, users["manager"], p["draft_id"], edits=edits, dish_map={"whte rice": rice.id}).json()
    assert done["rows_saved"] == 2 and done["rows_left_out"] == 1  # the dropped row is not counted as saved
    got = {r.menu_item_id: r.qty for r in db.scalars(select(SalesDaily).where(SalesDaily.date == date(2026, 10, 22)))}
    assert got == {rice.id: 12, egg.id: 9}  # the two typo rows were added together after mapping


def test_nothing_is_saved_while_every_row_still_has_a_problem(client, db, users, loaded):
    before = sales_count(db)
    p = preview(client, users["manager"], "bad.csv", csv_file("2026-10-23,,White rice,3,", "2026-10-22,,Nonsense,3,")).json()
    assert p["rows_ok"] == 0  # 23 Oct is after "today" (22 Oct)
    r = confirm(client, users["manager"], p["draft_id"])
    assert r.status_code == 422 and sales_count(db) == before


# ---------- PDF, read by AI ----------
PDF = b"%PDF-1.4 fake sales report"


def test_pdf_is_read_by_ai_checked_by_a_person_and_saved(client, db, users, loaded, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    seen = {}

    def fake(prompt, variables, schema, pdf_bytes, filename):
        seen.update(prompt=prompt, pdf=pdf_bytes, filename=filename, today=variables["today"])
        return {"rows": [{"date": "2026-10-22", "dish": "White rice", "qty": 10, "amount": 12.0},
                         {"date": "2026-10-22", "dish": "Unknown thing", "qty": 3, "amount": 0}], "notes": "page 2 is blurry"}

    monkeypatch.setattr(llm, "complete_json_with_pdf", fake)
    r = preview(client, users["manager"], "report.pdf", PDF, "application/pdf")
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["kind"], p["read_by_ai"], p["notes"], p["rows_ok"], p["problems"]) == ("pdf", True, "page 2 is blurry", 1, 1)
    assert seen == {"prompt": "sales_pdf", "pdf": PDF, "filename": "report.pdf", "today": "2026-10-22"}
    done = confirm(client, users["manager"], p["draft_id"]).json()
    assert done["rows_saved"] == 1
    log = db.scalars(select(ActivityLog).where(ActivityLog.action == "sales_imported")).all()[-1]
    assert log.details["type"] == "pdf" and log.details["read_by_ai"] is True
    ov = client.get("/api/sales/overview", headers=as_user(users["manager"])).json()
    assert ov["imports"][0]["kind"] == "pdf" and ov["imports"][0]["read_by_ai"] is True and ov["ai_available"] is True


def test_pdf_falls_back_to_csv_when_the_ai_is_off_fails_or_finds_nothing(client, users, loaded, monkeypatch):
    h = users["manager"]
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    r = preview(client, h, "report.pdf", PDF, "application/pdf")
    assert r.status_code == 503 and "CSV or Excel" in r.json()["detail"]
    assert client.get("/api/sales/overview", headers=as_user(h)).json()["ai_available"] is False

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    monkeypatch.setattr(llm, "complete_json_with_pdf", lambda *a, **k: None)
    r = preview(client, h, "report.pdf", PDF, "application/pdf")
    assert r.status_code == 502 and "CSV or Excel" in r.json()["detail"]

    monkeypatch.setattr(llm, "complete_json_with_pdf", lambda *a, **k: {"rows": [], "notes": "the page is blank"})
    r = preview(client, h, "report.pdf", PDF, "application/pdf")
    assert r.status_code == 422 and "blank" in r.json()["detail"]


# ---------- replace, remove, restore, delete forever ----------
def test_a_replaced_day_is_kept_aside_and_can_be_brought_back(client, db, users, loaded, background):
    h = users["manager"]
    day = date(2026, 10, 20)
    original = {r.menu_item_id: r.qty for r in db.scalars(select(SalesDaily).where(SalesDaily.date == day))}
    done = import_csv(client, h, "2026-10-20,,White rice,5,6")
    assert done["replaced_days"] == 1 and sales_count(db, day) == 1  # the file's day replaced the old day

    ov = client.get("/api/sales/overview", headers=as_user(h)).json()
    replaced = next(r for r in ov["removed"] if r["label"].startswith("Replaced by"))
    assert replaced["rows"] == len(original)

    # take the wrong file out; the day is empty; now the old numbers can come back
    out = client.post("/api/sales/remove", json={"import_id": done["import_id"]}, headers=as_user(h))
    assert out.status_code == 200 and sales_count(db, day) == 0
    assert client.post("/api/sales/remove", json={"import_id": done["import_id"]}, headers=as_user(h)).status_code == 409
    back = client.post(f"/api/sales/removals/{replaced['id']}/restore", headers=as_user(h))
    assert back.status_code == 200, back.text
    assert {r.menu_item_id: r.qty for r in db.scalars(select(SalesDaily).where(SalesDaily.date == day))} == original
    assert db.scalar(select(func.count()).select_from(SalesDailyRemoved).where(SalesDailyRemoved.removal_id == replaced["id"])) == 0
    assert {"sales_removed", "sales_restored"} <= set(actions(db)) and background == ["sales_change", "sales_change"]
    assert client.post(f"/api/sales/removals/{replaced['id']}/restore", headers=as_user(h)).status_code == 409  # already back


def test_restore_is_refused_when_the_days_have_been_filled_again(client, db, users, loaded):
    h = users["manager"]
    day = date(2026, 10, 19)
    r = client.post("/api/sales/remove", json={"date_from": "2026-10-19", "date_to": "2026-10-19"}, headers=as_user(h)).json()
    assert sales_count(db, day) == 0
    import_csv(client, h, "2026-10-19,,White rice,4,")  # the day is filled again with other numbers
    refused = client.post(f"/api/sales/removals/{r['removal']['id']}/restore", headers=as_user(h))
    assert refused.status_code == 409 and "2026-10-19" in refused.json()["detail"]
    assert sales_count(db, day) == 1  # nothing was overwritten


def test_remove_preview_says_where_today_moves_and_a_demo_date_keeps_it(client, db, users, loaded):
    h, owner = users["manager"], users["owner"]
    q = {"date_from": "2026-10-19", "date_to": "2026-10-21"}
    p = client.get("/api/sales/remove/preview", params=q, headers=as_user(h)).json()
    assert (p["days"], p["today_now"], p["today_after"]) == (3, "2026-10-22", "2026-10-19")  # latest left is 18 Oct
    client.patch("/api/settings", json={"today_override": "2026-10-20"}, headers=as_user(owner))
    p = client.get("/api/sales/remove/preview", params=q, headers=as_user(h)).json()
    assert p["today_now"] == "2026-10-20" and p["today_after"] is None
    assert client.get("/api/sales/remove/preview", params={"date_from": "2030-01-01", "date_to": "2030-01-02"}, headers=as_user(h)).status_code == 409
    assert client.get("/api/sales/remove/preview", headers=as_user(h)).status_code == 422


def test_only_the_owner_can_delete_forever_and_it_cannot_be_restored_after(client, db, users, loaded):
    h, owner = users["manager"], users["owner"]
    r = client.post("/api/sales/remove", json={"date_from": "2026-10-21", "date_to": "2026-10-21"}, headers=as_user(h)).json()["removal"]
    url = f"/api/sales/removals/{r['id']}"
    assert client.delete(url, headers=as_user(h)).status_code == 403
    assert client.delete(url, headers=as_user(owner)).status_code == 200
    assert db.scalar(select(func.count()).select_from(SalesDailyRemoved)) == 0
    assert client.post(url + "/restore", headers=as_user(h)).status_code == 409
    assert "sales_deleted_forever" in actions(db)
    ov = client.get("/api/sales/overview", headers=as_user(h)).json()
    assert all(x["id"] != r["id"] for x in ov["removed"])


def test_roles_and_login_are_checked(client, users, loaded):
    assert preview(client, users["staff"], "s.csv", csv_file("2026-10-22,,White rice,1,")).status_code == 403
    assert client.post("/api/sales/remove", json={"date_from": "2026-10-21", "date_to": "2026-10-21"}, headers=as_user(users["staff"])).status_code == 403
    assert client.get("/api/sales/overview", headers=as_user(users["staff"])).status_code == 200  # everyone can look
    assert client.get("/api/sales/overview").status_code == 401
    assert client.get("/api/sales/template.csv", headers=as_user(users["staff"])).text.startswith("Date,Item Code")


def test_removing_sales_recomputes_buffers_and_a_big_catch_up_does_too(client, db, users, loaded, background):
    h = users["manager"]
    client.post("/api/sales/remove", json={"date_from": "2026-10-21", "date_to": "2026-10-21"}, headers=as_user(h))
    assert background == ["sales_change"]
    lines = [f"2026-10-{d:02d},,White rice,3," for d in range(22, 23)]
    import_csv(client, h, *lines)
    assert background == ["sales_change"]  # a single new day does not
    # eight days that are new to the app (days before the history started) do
    many = [f"2025-10-{d:02d},,White rice,3," for d in range(10, 18)]
    import_csv(client, h, *many, name="old.csv")
    assert background == ["sales_change", "sales_import"]


# ---------- plans made before the data changed ----------
def test_plans_and_draft_orders_say_when_sales_changed_after_they_were_made(client, db, users, loaded, background):
    m = users["manager"]
    plan = make_plan(client, users, 3)
    assert plan["data_changed_since"] is False and all(o["plan_is_stale"] is False for o in plan["orders"])
    submitted = plan["orders"][0]["id"]
    act(client, m, submitted, "submit")

    client.post("/api/sales/remove", json={"date_from": "2026-10-21", "date_to": "2026-10-21"}, headers=as_user(m))
    again = client.get(f"/api/planning/plans/{plan['id']}", headers=as_user(m)).json()
    assert again["data_changed_since"] is True
    states = {o["id"]: o["plan_is_stale"] for o in again["orders"]}
    assert states[submitted] is True and all(states.values())  # draft and waiting-for-approval orders are flagged

    act(client, users["owner"], submitted, "approve")
    approved = next(o for o in client.get(f"/api/planning/plans/{plan['id']}", headers=as_user(m)).json()["orders"] if o["id"] == submitted)
    assert approved["plan_is_stale"] is False  # an approved order is a real decision; it is not flagged

    fresh = make_plan(client, users, 3)
    assert fresh["data_changed_since"] is False and all(o["plan_is_stale"] is False for o in fresh["orders"])


# ---------- first-time setup: the sales history step ----------
def test_setup_needs_enough_sales_history_and_the_demo_has_it(client, db, users, loaded):
    owner = users["owner"]
    client.post("/api/setup/country", json={"country": "MY"}, headers=as_user(owner))
    s = client.get("/api/setup/status", headers=as_user(owner)).json()
    assert (s["step"], s["sales_done"]) == ("sales", False)
    assert client.post("/api/setup/sales/confirm", headers=as_user(users["manager"])).status_code == 403

    # a business with only a week of sales cannot go on
    keep = db.scalars(select(SalesDaily.date).distinct().order_by(SalesDaily.date.desc()).limit(7)).all()
    from sqlalchemy import delete
    db.execute(delete(SalesDaily).where(SalesDaily.date.notin_(keep)))
    db.commit()
    r = client.post("/api/setup/sales/confirm", headers=as_user(owner))
    assert r.status_code == 409 and "28" in r.json()["detail"] and "7" in r.json()["detail"]
    assert client.get("/api/setup/status", headers=as_user(owner)).json()["step"] == "sales"
