"""The order note: written when the owner approves, saved with the order, and sent exactly as approved."""
from datetime import date

from sqlalchemy import select

from app.modules.activity.models import ActivityLog
from app.modules.planning.models import PurchaseOrder
from app.modules.planning.whatsapp import build_order_note
from tests.conftest import as_user
from tests.test_planning import act, make_plan


def test_approving_writes_the_note_with_prices_and_the_total(client, db, users, loaded):
    plan = make_plan(client, users, 3)
    order = plan["orders"][0]
    act(client, users["manager"], order["id"], "submit")
    assert client.get(f"/api/planning/orders/{order['id']}", headers=as_user(users["manager"])).json()["note_text"] is None

    approved = act(client, users["owner"], order["id"], "approve").json()
    note = approved["note_text"]
    assert note.startswith(f"PURCHASE ORDER PO-{order['id']:04d}")
    assert "Kopitiam Demo (AIMST)" in note and order["supplier_name"] in note and "Delivery on " in note
    for line in order["lines"]:
        assert line["name"] in note
    assert f"ORDER TOTAL: RM {order['total_rm']:,.2f}" in note
    assert "x RM" in note and "= RM" in note  # every line carries its price and its line total
    assert db.get(PurchaseOrder, order["id"]).note_text == note
    log = db.scalars(select(ActivityLog).where(ActivityLog.action == "po_approved")).one()
    assert log.details["note_prepared"] is True

    sent = act(client, users["owner"], order["id"], "send").json()
    assert sent["whatsapp_text"] == note  # what was approved is what is sent
    assert client.get(f"/api/planning/orders/{order['id']}", headers=as_user(users["staff"])).json()["note_text"] == note  # visible in history


def test_the_saved_note_does_not_change_when_the_supplier_is_edited_later(client, db, users, loaded):
    order = make_plan(client, users, 3)["orders"][0]
    act(client, users["manager"], order["id"], "submit")
    note = act(client, users["owner"], order["id"], "approve").json()["note_text"]
    client.patch(f"/api/settings/suppliers/{order['supplier_id']}", json={"min_order_rm": 999}, headers=as_user(users["owner"]))
    assert act(client, users["owner"], order["id"], "send").json()["whatsapp_text"] == note


def test_an_order_approved_before_notes_were_saved_still_gets_one(client, db, users, loaded):
    order = make_plan(client, users, 3)["orders"][0]
    act(client, users["manager"], order["id"], "submit")
    act(client, users["owner"], order["id"], "approve")
    po = db.get(PurchaseOrder, order["id"])
    po.note_text = None  # as if approved by an older version of the app
    db.commit()
    text = act(client, users["owner"], order["id"], "send").json()["whatsapp_text"]
    assert text.startswith("PURCHASE ORDER PO-") and f"ORDER TOTAL: RM {order['total_rm']:,.2f}" in text


def test_note_groups_lines_by_delivery_day_with_subtotals():
    note = build_order_note(
        12, "Pasar Borong", "Kopitiam Demo", date(2026, 10, 22),
        [{"name": "Eggs", "pack_uom": "TRAY (30 pcs)", "pack_price_rm": 12.5,
          "schedule": [{"date": "2026-10-23", "packs": 4}, {"date": "2026-10-26", "packs": 1}]},
         {"name": "Ice cubes", "pack_uom": "BAG (10kg)", "pack_price_rm": 6.0, "schedule": [{"date": "2026-10-23", "packs": 2}]}],
        74.5,
    )
    lines = note.splitlines()
    assert lines[0] == "PURCHASE ORDER PO-0012" and lines[1] == "From: Kopitiam Demo" and lines[2] == "To: Pasar Borong"
    assert lines[3] == "Date: Thu 22 Oct 2026"
    assert lines.index("Delivery on Fri 23 Oct:") < lines.index("Delivery on Mon 26 Oct:")
    assert "1. Eggs - 4 TRAY (30 pcs) x RM 12.50 = RM 50.00" in lines
    assert "2. Ice cubes - 2 BAG (10kg) x RM 6.00 = RM 12.00" in lines
    assert "1. Eggs - 1 TRAY (30 pcs) x RM 12.50 = RM 12.50" in lines  # the later delivery has its own numbering
    assert "Subtotal for this delivery: RM 62.00" in lines and "Subtotal for this delivery: RM 12.50" in lines
    assert "ORDER TOTAL: RM 74.50" in note
