from datetime import datetime

import pytest

from app.modules.planning.models import ForecastQuality
from tests.conftest import as_user


def make_plan(client, users, horizon=3):
    return client.post("/api/planning/plans", json={"horizon_days": horizon}, headers=as_user(users["manager"])).json()


def approve(client, users, order_id):
    client.post(f"/api/planning/orders/{order_id}/submit", headers=as_user(users["manager"]))
    return client.post(f"/api/planning/orders/{order_id}/approve", headers=as_user(users["owner"]))


def test_dashboard_before_any_plan(client, users, loaded):
    d = client.get("/api/dashboard", headers=as_user(users["staff"])).json()
    assert d["plans_total"] == 0 and d["plans_completed"] == 0 and d["hours_saved"] == 0
    assert d["last_plan"] is None and d["accuracy"] is None and d["orders"] == [] and d["top_spend"] == []
    assert d["avg_review_minutes"] is None and d["manual_hours_per_plan"] == 16
    inv = d["inventory"]
    assert inv["expired"] == 3 and sorted(inv["expired_items"])[0] == "Fresh milk" and inv["expiring_soon"] >= 1
    assert inv["ok"] + inv["expired"] + inv["expiring_soon"] == 74


def test_dashboard_requires_login(client, loaded):
    assert client.get("/api/dashboard").status_code == 401


def test_planning_context(client, users, loaded):
    h = as_user(users["staff"])
    assert client.get("/api/planning/context", headers=h).json() == {"today": "2026-10-22", "last_plan_id": None}
    plan = make_plan(client, users)
    assert client.get("/api/planning/context", headers=h).json()["last_plan_id"] == plan["id"]


def test_time_saved_counts_only_plans_that_reached_approval(client, users, loaded):
    first = make_plan(client, users)
    d = client.get("/api/dashboard", headers=as_user(users["owner"])).json()
    assert d["plans_total"] == 1 and d["plans_completed"] == 0 and d["hours_saved"] == 0  # generated, not approved

    assert approve(client, users, first["orders"][0]["id"]).status_code == 200
    d = client.get("/api/dashboard", headers=as_user(users["owner"])).json()
    assert d["plans_completed"] == 1
    assert 15.9 < d["hours_saved"] <= 16  # 16 manual hours minus a few seconds of review
    assert 0 <= d["avg_review_minutes"] < 1

    second = make_plan(client, users, 2)  # a second plan nobody approved yet
    d = client.get("/api/dashboard", headers=as_user(users["owner"])).json()
    assert d["plans_total"] == 2 and d["plans_completed"] == 1
    assert d["last_plan"]["id"] == second["id"] and d["last_plan"]["horizon_days"] == 2
    assert d["last_plan"]["grand_total_rm"] == pytest.approx(second["grand_total_rm"])

    approve(client, users, second["orders"][0]["id"])
    d = client.get("/api/dashboard", headers=as_user(users["owner"])).json()
    assert d["plans_completed"] == 2 and 31.8 < d["hours_saved"] <= 32


def test_order_status_per_supplier_and_top_spend(client, users, loaded):
    plan = make_plan(client, users, 5)
    approve(client, users, plan["orders"][0]["id"])
    d = client.get("/api/dashboard", headers=as_user(users["manager"])).json()
    by_id = {o["id"]: o for o in d["orders"]}
    assert set(by_id) == {o["id"] for o in plan["orders"]}
    assert by_id[plan["orders"][0]["id"]]["status"] == "approved"
    assert all(o["supplier_name"] for o in d["orders"])
    spend = d["top_spend"]
    assert 1 <= len(spend) <= 5 and [s["total_rm"] for s in spend] == sorted((s["total_rm"] for s in spend), reverse=True)
    biggest = max(l["line_total_rm"] for o in plan["orders"] for l in o["lines"])
    assert spend[0]["total_rm"] == pytest.approx(biggest)


def test_rejected_orders_do_not_count_as_spend(client, users, loaded):
    plan = make_plan(client, users, 3)
    for o in plan["orders"]:
        client.post(f"/api/planning/orders/{o['id']}/submit", headers=as_user(users["manager"]))
        client.post(f"/api/planning/orders/{o['id']}/reject", json={"reason": "no"}, headers=as_user(users["owner"]))
    d = client.get("/api/dashboard", headers=as_user(users["owner"])).json()
    assert d["top_spend"] == [] and d["plans_completed"] == 0


def test_accuracy_card_uses_the_stored_forecast_quality(client, db, users, loaded):
    db.add(ForecastQuality(tenant_id=1, computed_at=datetime.now(), model_name="calendar_topdown", horizon_days=7,
                           wape_total=0.131, wape_items=0.6, baseline_naive_wape=0.21, baseline_flat_wape=0.27))
    db.commit()
    acc = client.get("/api/dashboard", headers=as_user(users["owner"])).json()["accuracy"]
    assert acc == {"horizon_days": 7, "wape_total": 0.131, "baseline_naive_wape": 0.21, "baseline_flat_wape": 0.27}
