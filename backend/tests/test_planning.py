"""The planning workflow: generate -> edit -> submit -> approve -> send -> receive, with roles and logging."""
from datetime import date
from urllib.parse import unquote

import pytest
from sqlalchemy import select

from app.modules.activity.models import ActivityLog
from app.modules.inventory.models import InventoryBatch, InventoryItem, InventoryMovement
from app.modules.planning.models import ForecastLine, PlanRun, PurchaseOrder
from app.modules.planning.whatsapp import build_order_message, effective_schedule, whatsapp_number, whatsapp_url
from tests.conftest import as_user


def make_plan(client, users, horizon=3, **extra):
    r = client.post("/api/planning/plans", json={"horizon_days": horizon, **extra}, headers=as_user(users["manager"]))
    assert r.status_code == 201, r.text
    return r.json()


def act(client, user, order_id, action, **body):
    return client.post(f"/api/planning/orders/{order_id}/{action}", json=body or None, headers=as_user(user))


# ---------- generating ----------
def test_generate_plan_saves_run_forecast_and_one_draft_order_per_supplier(client, db, users, loaded):
    plan = make_plan(client, users, 3)
    assert plan["today"] == "2026-10-22" and plan["horizon_days"] == 3 and plan["created_by_name"] == users["manager"].name
    assert plan["duration_ms"] > 0 and plan["calc_count"] > 1000 and plan["risk_profile"] == "balanced"
    assert plan["manual_planning_hours"] == 16

    orders = plan["orders"]
    assert 1 <= len(orders) <= 3 and all(o["status"] == "draft" for o in orders)
    assert len({o["supplier_id"] for o in orders}) == len(orders)
    for o in orders:
        assert o["total_rm"] == pytest.approx(sum(l["line_total_rm"] for l in o["lines"]))
        for l in o["lines"]:
            assert l["final_packs"] == l["suggested_packs"] > 0
            assert l["explanation"]["trips"] and l["buffer_pct"] >= 0 and l["display_buy"].startswith(str(l["final_packs"]))
    assert plan["grand_total_rm"] == pytest.approx(sum(o["total_rm"] for o in orders))

    # forecast: today + 3 days, with drivers, plus the last 28 days of real totals
    days = plan["forecast"]["days"]
    assert [d["is_today"] for d in days] == [True, False, False, False] and days[0]["weekday"] == "Thu"
    assert days[1]["drivers"]["state"] and days[1]["total"] > 0
    assert len(plan["forecast"]["history"]) == 29 and plan["forecast"]["history"][-1]["date"] == "2026-10-22"
    assert plan["forecast"]["dishes"][0]["qty"] and len(plan["forecast"]["dishes"][0]["qty"]) == 4

    # engine output stored
    assert db.get(PlanRun, plan["id"]).calc_count == plan["calc_count"]
    assert len(db.scalars(select(ForecastLine).where(ForecastLine.run_id == plan["id"])).all()) > 400
    # demo data: 3 expired items are on the discard list
    assert len(plan["discard"]) == 3
    # one log entry
    log = db.scalars(select(ActivityLog).where(ActivityLog.action == "plan_generated")).one()
    assert log.user_id == users["manager"].id and log.details["orders"] == len(orders)


def test_get_plan_matches_the_created_plan(client, users, loaded):
    plan = make_plan(client, users, 2)
    again = client.get(f"/api/planning/plans/{plan['id']}", headers=as_user(users["staff"]))  # staff may view
    assert again.status_code == 200 and again.json() == plan
    assert client.get("/api/planning/plans/9999", headers=as_user(users["staff"])).status_code == 404


def test_horizon_1_to_7_only_and_manager_needed(client, users, loaded):
    for bad in (0, 8):
        assert client.post("/api/planning/plans", json={"horizon_days": bad}, headers=as_user(users["manager"])).status_code == 422
    assert client.post("/api/planning/plans", json={"horizon_days": 3}, headers=as_user(users["staff"])).status_code == 403
    assert client.post("/api/planning/plans", json={"horizon_days": 3}).status_code == 401
    assert len(make_plan(client, users, 7)["forecast"]["days"]) == 8
    assert len(make_plan(client, users, 1)["forecast"]["days"]) == 2


def test_today_can_be_overridden(client, users, loaded):
    plan = make_plan(client, users, 2, today="2026-10-20")
    assert plan["today"] == "2026-10-20" and plan["forecast"]["history"][-1]["date"] == "2026-10-20"


def test_longer_horizons_cost_more(client, users, loaded):
    assert make_plan(client, users, 7)["grand_total_rm"] > make_plan(client, users, 2)["grand_total_rm"]


# ---------- editing ----------
def first_line(plan):
    order = plan["orders"][0]
    return order, order["lines"][0]


def test_edit_line_updates_totals_and_logs_before_and_after(client, db, users, loaded):
    plan = make_plan(client, users, 3)
    order, line = first_line(plan)
    new = line["suggested_packs"] + 2
    r = client.patch(f"/api/planning/orders/{order['id']}/lines/{line['id']}", json={"final_packs": new},
                     headers=as_user(users["manager"]))
    assert r.status_code == 200
    got = r.json()
    edited = next(l for l in got["lines"] if l["id"] == line["id"])
    assert edited["final_packs"] == new and edited["suggested_packs"] == line["suggested_packs"]
    assert edited["line_total_rm"] == pytest.approx(new * line["pack_price_rm"])
    assert edited["leftover_base"] == pytest.approx(line["leftover_base"] + 2 * line["pack_size_base"])  # 2 extra packs
    assert got["total_rm"] == pytest.approx(sum(l["line_total_rm"] for l in got["lines"]))
    log = db.scalars(select(ActivityLog).where(ActivityLog.action == "po_line_edited")).one()
    assert log.details["before"]["final_packs"] == line["suggested_packs"] and log.details["after"]["final_packs"] == new
    assert log.user_id == users["manager"].id
    # setting the same value again is not logged
    client.patch(f"/api/planning/orders/{order['id']}/lines/{line['id']}", json={"final_packs": new}, headers=as_user(users["manager"]))
    assert len(db.scalars(select(ActivityLog).where(ActivityLog.action == "po_line_edited")).all()) == 1


def test_edit_rules(client, users, loaded):
    plan = make_plan(client, users, 3)
    order, line = first_line(plan)
    url = f"/api/planning/orders/{order['id']}/lines/{line['id']}"
    assert client.patch(url, json={"final_packs": 1}, headers=as_user(users["staff"])).status_code == 403
    assert client.patch(url, json={"final_packs": -1}, headers=as_user(users["manager"])).status_code == 422
    other = plan["orders"][-1]["lines"][0]["id"] if len(plan["orders"]) > 1 else 99999
    assert client.patch(f"/api/planning/orders/{order['id']}/lines/{other}", json={"final_packs": 1},
                        headers=as_user(users["manager"])).status_code == 404
    act(client, users["manager"], order["id"], "submit")
    assert client.patch(url, json={"final_packs": 1}, headers=as_user(users["manager"])).status_code == 409  # no longer a draft


def test_cannot_submit_an_order_with_nothing_in_it(client, users, loaded):
    order = make_plan(client, users, 1)["orders"][0]
    for l in order["lines"]:
        client.patch(f"/api/planning/orders/{order['id']}/lines/{l['id']}", json={"final_packs": 0}, headers=as_user(users["manager"]))
    assert act(client, users["manager"], order["id"], "submit").status_code == 409


# ---------- the full journey ----------
def test_full_journey_with_roles_inventory_and_activity_log(client, db, users, loaded):
    # 1. manager generates and edits
    plan = make_plan(client, users, 3)
    order, line = first_line(plan)
    oid = order["id"]
    packs = line["suggested_packs"] + 1
    client.patch(f"/api/planning/orders/{oid}/lines/{line['id']}", json={"final_packs": packs}, headers=as_user(users["manager"]))

    # 2. manager submits
    sub = act(client, users["manager"], oid, "submit")
    assert sub.status_code == 200 and sub.json()["status"] == "pending_approval"

    # 3. staff and manager cannot approve; the owner can
    assert act(client, users["staff"], oid, "approve").status_code == 403
    assert act(client, users["manager"], oid, "approve").status_code == 403
    appr = act(client, users["owner"], oid, "approve").json()
    assert appr["status"] == "approved" and appr["approved_by_name"] == users["owner"].name and appr["approved_at"]

    # 4. only the owner sends; the link carries the order
    assert act(client, users["manager"], oid, "send").status_code == 403
    sent = act(client, users["owner"], oid, "send").json()
    assert sent["order"]["status"] == "sent" and sent["order"]["sent_at"]
    assert sent["whatsapp_url"].startswith("https://wa.me/601000000")
    assert unquote(sent["whatsapp_url"].split("?text=")[1]) == sent["whatsapp_text"]
    prefix = f"- {line['name']} – "  # trips for one item may be listed under several delivery dates
    in_message = [int(t[len(prefix):].split()[0]) for t in sent["whatsapp_text"].splitlines() if t.startswith(prefix)]
    assert sum(in_message) == packs  # the edited pack count, not the suggested one
    assert f"Total: RM {sent['order']['total_rm']:,.2f}" in sent["whatsapp_text"]

    # 5. staff cannot receive; manager can, and stock goes up
    ing_id = line["ingredient_id"]
    inv = db.scalars(select(InventoryItem).where(InventoryItem.ingredient_id == ing_id)).one()
    before = inv.qty_base
    assert act(client, users["staff"], oid, "receive").status_code == 403
    rec = act(client, users["manager"], oid, "receive").json()
    assert rec["status"] == "received" and rec["received_at"]
    db.refresh(inv)
    assert inv.qty_base == pytest.approx(before + packs * line["pack_size_base"])
    assert inv.last_purchased_on.isoformat() == "2026-10-22"
    move = db.scalars(select(InventoryMovement).where(InventoryMovement.reason == "received",
                                                      InventoryMovement.ingredient_id == ing_id)).one()
    assert move.change_base == pytest.approx(packs * line["pack_size_base"]) and move.user_id == users["manager"].id

    # 6. every step is in the activity log, with the right person
    logs = db.scalars(select(ActivityLog).order_by(ActivityLog.id)).all()
    steps = [(l.action, l.role) for l in logs]
    assert steps == [
        ("plan_generated", "manager"), ("po_line_edited", "manager"), ("po_submitted", "manager"),
        ("po_approved", "owner"), ("po_sent", "owner"), ("po_received", "manager"),
    ]
    assert all(l.entity_id for l in logs)
    assert logs[-1].details["lines"] and logs[-1].user_id == users["manager"].id
    # and the manager can read them through the API
    api = client.get("/api/activity", headers=as_user(users["manager"])).json()
    assert [a["action"] for a in api][0] == "po_received"


def test_receiving_adds_a_new_batch_and_keeps_expired_stock_separate(client, db, users, loaded):
    plan = make_plan(client, users, 5)
    expired_ids = {d["ingredient_id"] for d in plan["discard"]}
    order, line = next(
        (o, l) for o in plan["orders"] for l in o["lines"] if l["ingredient_id"] in expired_ids
    )  # a delivery of something whose old stock has already expired
    ing_id = line["ingredient_id"]
    old = db.scalars(select(InventoryBatch).where(InventoryBatch.ingredient_id == ing_id)).one()
    old_date, old_qty = old.procured_on, old.qty_base
    act(client, users["manager"], order["id"], "submit")
    act(client, users["owner"], order["id"], "approve")
    act(client, users["owner"], order["id"], "send")
    assert act(client, users["manager"], order["id"], "receive").status_code == 200
    batches = db.scalars(select(InventoryBatch).where(InventoryBatch.ingredient_id == ing_id)
                         .order_by(InventoryBatch.procured_on)).all()
    assert [b.procured_on for b in batches] == [old_date, date(2026, 10, 22)]  # the old batch keeps its own date
    assert batches[0].qty_base == old_qty
    assert batches[1].qty_base == pytest.approx(line["final_packs"] * line["pack_size_base"])
    assert batches[1].pack_price_rm == line["pack_price_rm"]
    row = next(i for i in client.get("/api/inventory", headers=as_user(users["manager"])).json()["items"]
               if i["ingredient_id"] == ing_id)
    assert [b["status"] for b in row["batches"]] == ["expired", "ok"] and row["status"] == "expired"
    inv = db.scalars(select(InventoryItem).where(InventoryItem.ingredient_id == ing_id)).one()
    db.refresh(inv)
    assert inv.qty_base == pytest.approx(old_qty + line["final_packs"] * line["pack_size_base"])


def test_receiving_an_approved_order_does_not_require_a_whatsapp_send(client, db, users, loaded):
    plan = make_plan(client, users, 3)
    order = plan["orders"][0]
    line = order["lines"][0]
    assert act(client, users["manager"], order["id"], "submit").status_code == 200
    assert act(client, users["owner"], order["id"], "approve").status_code == 200

    received = act(client, users["manager"], order["id"], "receive")
    assert received.status_code == 200 and received.json()["status"] == "received"

    batches = db.scalars(
        select(InventoryBatch).where(InventoryBatch.ingredient_id == line["ingredient_id"])
    ).all()
    assert any(
        batch.procured_on == date(2026, 10, 22)
        and batch.qty_base == pytest.approx(line["final_packs"] * line["pack_size_base"])
        for batch in batches
    )


def test_reject_needs_a_reason_and_is_final(client, db, users, loaded):
    oid = make_plan(client, users, 3)["orders"][0]["id"]
    act(client, users["manager"], oid, "submit")
    assert act(client, users["manager"], oid, "reject", reason="Too much").status_code == 403
    assert act(client, users["owner"], oid, "reject").status_code == 422
    assert act(client, users["owner"], oid, "reject", reason="").status_code == 422
    r = act(client, users["owner"], oid, "reject", reason="Too much for a quiet week").json()
    assert r["status"] == "rejected" and r["reject_reason"] == "Too much for a quiet week"
    for step in ("submit", "approve", "send", "receive"):
        assert act(client, users["owner"], oid, step).status_code == 409
    log = db.scalars(select(ActivityLog).where(ActivityLog.action == "po_rejected")).one()
    assert log.details["reason"] == "Too much for a quiet week" and log.role == "owner"


def test_invalid_transitions_are_409(client, users, loaded):
    oid = make_plan(client, users, 3)["orders"][0]["id"]
    for step, who in (("approve", "owner"), ("send", "owner"), ("receive", "manager")):
        assert act(client, users[who], oid, step).status_code == 409, step  # a draft cannot jump ahead
    act(client, users["manager"], oid, "submit")
    assert act(client, users["manager"], oid, "submit").status_code == 409  # already submitted
    assert act(client, users["owner"], oid, "send").status_code == 409  # not approved yet
    assert act(client, users["manager"], oid, "receive").status_code == 409
    act(client, users["owner"], oid, "approve")
    assert act(client, users["owner"], oid, "approve").status_code == 409
    assert act(client, users["owner"], oid, "reject", reason="x").status_code == 409


def test_sending_twice_returns_the_same_message_without_a_second_log(client, db, users, loaded):
    oid = make_plan(client, users, 3)["orders"][0]["id"]
    act(client, users["manager"], oid, "submit")
    act(client, users["owner"], oid, "approve")
    first = act(client, users["owner"], oid, "send").json()
    again = act(client, users["owner"], oid, "send").json()
    assert again["whatsapp_url"] == first["whatsapp_url"] and again["order"]["status"] == "sent"
    assert len(db.scalars(select(ActivityLog).where(ActivityLog.action == "po_sent")).all()) == 1


def test_message_preview_keeps_the_order_in_draft_until_confirmed(client, db, users, loaded):
    order = make_plan(client, users, 3)["orders"][0]
    preview = client.get(f"/api/planning/orders/{order['id']}/message", headers=as_user(users["owner"]))

    assert preview.status_code == 200
    result = preview.json()
    assert result["order"]["status"] == "draft"
    assert result["order"]["id"] == order["id"]
    assert order["supplier_name"] in result["whatsapp_text"]
    assert f"Total: RM {order['total_rm']:,.2f}" in result["whatsapp_text"]
    assert client.get(f"/api/planning/orders/{order['id']}", headers=as_user(users["manager"])).json()["status"] == "draft"
    assert not db.scalars(select(ActivityLog).where(ActivityLog.action == "po_sent")).all()
    assert client.get(f"/api/planning/orders/{order['id']}/message", headers=as_user(users["manager"])).status_code == 403


def test_orders_list_filter_and_detail(client, users, loaded):
    plan = make_plan(client, users, 3)
    ids = [o["id"] for o in plan["orders"]]
    act(client, users["manager"], ids[0], "submit")
    h = as_user(users["staff"])
    assert {o["id"] for o in client.get("/api/planning/orders", headers=h).json()} == set(ids)
    pending = client.get("/api/planning/orders?status=pending_approval", headers=h).json()
    assert [o["id"] for o in pending] == [ids[0]]
    assert client.get("/api/planning/orders?status=sent", headers=h).json() == []
    assert client.get(f"/api/planning/orders/{ids[0]}", headers=h).json()["status"] == "pending_approval"
    assert client.get("/api/planning/orders/9999", headers=h).status_code == 404


def test_orders_belong_to_a_tenant(client, db, users, loaded):
    from app.modules.settings.models import Tenant, User

    other = Tenant(name="Other cafe")
    db.add(other)
    db.flush()
    stranger = User(tenant_id=other.id, name="Zed", role="owner")
    db.add(stranger)
    db.commit()
    oid = make_plan(client, users, 2)["orders"][0]["id"]
    assert client.get(f"/api/planning/orders/{oid}", headers=as_user(stranger)).status_code == 404
    assert act(client, stranger, oid, "approve").status_code == 404
    assert client.get("/api/planning/orders", headers=as_user(stranger)).json() == []


def test_below_minimum_order_shows_a_warning(client, db, users, loaded):
    from app.modules.catalog.models import Supplier

    for s in db.scalars(select(Supplier)):
        s.min_order_rm = 1_000_000
    db.commit()
    orders = make_plan(client, users, 1)["orders"]
    assert orders and all(o["warnings"] and "minimum order" in o["warnings"][0] for o in orders)


# ---------- WhatsApp text ----------
def test_effective_schedule_spreads_edits_over_trips():
    trips = [{"date": "2026-10-23", "packs": 2}, {"date": "2026-10-25", "packs": 1}, {"date": "2026-10-27", "packs": 3}]
    assert effective_schedule(trips, 6, 6) == trips
    assert effective_schedule(trips, 6, 8)[0]["packs"] == 4  # extra packs go on the first trip
    assert effective_schedule(trips, 6, 4) == [{"date": "2026-10-23", "packs": 2}, {"date": "2026-10-25", "packs": 1},
                                                {"date": "2026-10-27", "packs": 1}]  # taken off the latest trip
    assert effective_schedule(trips, 6, 2) == [{"date": "2026-10-23", "packs": 2}]
    assert effective_schedule(trips, 6, 0) == []


def test_whatsapp_message_groups_by_delivery_date():
    text = build_order_message(
        "Pasar Borong", "Kopitiam Demo",
        [{"name": "Eggs", "pack_uom": "TRAY (30 pcs)", "schedule": [{"date": "2026-10-23", "packs": 4}, {"date": "2026-10-26", "packs": 3}]},
         {"name": "Ice cubes", "pack_uom": "BAG (10kg)", "schedule": [{"date": "2026-10-23", "packs": 2}]}],
        98.5,
    )
    assert text.splitlines() == [
        "Hello Pasar Borong, this is Kopitiam Demo.",
        "Order for Fri 23 Oct:", "- Eggs – 4 TRAY (30 pcs)", "- Ice cubes – 2 BAG (10kg)",
        "Order for Mon 26 Oct:", "- Eggs – 3 TRAY (30 pcs)",
        "Total: RM 98.50", "Thank you! – Kopitiam Demo",
    ]


def test_whatsapp_url_and_number():
    assert whatsapp_number("+60 10-000 0001") == "60100000001"
    assert whatsapp_number("") is None and whatsapp_url(None, "hi") is None
    assert whatsapp_url("60100000001", "Hi there & more") == "https://wa.me/60100000001?text=Hi%20there%20%26%20more"


def test_a_restaurant_closed_every_monday_still_gets_a_plan_and_buffers(client, db, users, loaded):
    """End to end: no sales on Mondays at all (a closed day), then measure buffers and plan a week that contains a Monday."""
    from sqlalchemy import delete

    from app.modules.planning.quality import recompute_safety
    from app.modules.sales.models import SalesDaily
    from app.modules.settings.models import Tenant

    monday_ids = [r.id for r in db.scalars(select(SalesDaily)) if r.date.weekday() == 0]
    assert monday_ids
    for i in range(0, len(monday_ids), 500):
        db.execute(delete(SalesDaily).where(SalesDaily.id.in_(monday_ids[i : i + 500])))
    db.commit()

    summary = recompute_safety(db, db.get(Tenant, users["owner"].tenant_id))
    db.commit()
    assert summary["origins"] > 0 and summary["profiles"] > 0

    plan = make_plan(client, users, 7)  # today is Thu 22 Oct, so the week includes Monday 26 Oct
    days = {d["date"]: d["total"] for d in plan["forecast"]["days"]}
    assert all(v == v and v >= 0 for v in days.values())  # no NaN, nothing negative
    assert days["2026-10-26"] == 0  # the closed Monday
    assert days["2026-10-27"] > 100 and days["2026-10-23"] > 100  # the days around it are normal
    assert plan["grand_total_rm"] == plan["grand_total_rm"] and plan["grand_total_rm"] > 0
    for order in plan["orders"]:
        for line in order["lines"]:
            assert line["final_packs"] > 0 and line["line_total_rm"] == line["line_total_rm"]
            assert 0 <= line["buffer_pct"] <= 60
