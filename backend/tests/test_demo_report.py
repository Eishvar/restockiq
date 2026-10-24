"""The pre-made sales report for Thu 22 Oct (data/demo_reports): upload it, then plan from the next day.

The AI that reads PDFs is replaced by a stand-in that copies the printed lines, so these tests prove the file, the
matching of dish names and the effect on the app's date. They cannot prove how well the real AI reads this PDF.
"""
import importlib.util
import re
import sys
from datetime import date

import pytest
from sqlalchemy import func, select

from app.ai import llm
from app.config import REPO_ROOT
from app.modules.sales.models import SalesDaily
from tests.conftest import as_user
from tests.test_planning import make_plan
from tests.test_sales_data import confirm, preview

REPORTS = REPO_ROOT / "data" / "demo_reports"
PDF_FILE = REPORTS / "sales_report_2026-10-22.pdf"
CSV_FILE = REPORTS / "sales_report_2026-10-22.csv"
LINE = re.compile(r"^(\d\d)/(\d\d)/(\d{4})\s+(M\d+)\s+(.+?)\s+(\d+)\s+RM ([\d,.]+)$")


def printed_lines(pdf: bytes) -> list[re.Match]:
    texts = [re.sub(r"\\(.)", r"\1", t.decode("latin-1")) for t in re.findall(rb"\(((?:\\.|[^\\])*?)\) Tj", pdf)]
    return [m for m in (LINE.match(t) for t in texts) if m]


def fake_reader(monkeypatch, with_code: bool):
    """Stands in for the AI: copies each printed line into a row, the way the prompt asks."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")

    def read(prompt, variables, schema, pdf_bytes, filename):
        rows = [{"date": f"{m[3]}-{m[2]}-{m[1]}", "dish": f"{m[4]} {m[5]}" if with_code else m[5],
                 "qty": int(m[6]), "amount": float(m[7].replace(",", ""))} for m in printed_lines(pdf_bytes)]
        return {"rows": rows, "notes": ""}

    monkeypatch.setattr(llm, "complete_json_with_pdf", read)


def test_the_sample_files_are_there_and_the_pdf_has_real_text():
    pdf = PDF_FILE.read_bytes()
    assert pdf.startswith(b"%PDF") and pdf.rstrip().endswith(b"%%EOF")
    lines = printed_lines(pdf)
    assert len(lines) > 50 and all(m.group(1, 2, 3) == ("22", "10", "2026") for m in lines)
    assert any(m[5] == "White rice" for m in lines)
    assert b"Demo helper: simulated report" in pdf
    assert len(CSV_FILE.read_text(encoding="utf-8").splitlines()) == len(lines) + 1


def test_the_script_makes_exactly_these_files_again(tmp_path):
    spec = importlib.util.spec_from_file_location("make_demo_report", REPO_ROOT / "data" / "make_demo_report.py")
    sys.path.insert(0, str(REPO_ROOT / "data"))
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(REPO_ROOT / "data"))
    day = date(2026, 10, 22)
    assert mod.build_pdf(day, mod.make_day(day)) == PDF_FILE.read_bytes()


@pytest.mark.parametrize("with_code", [True, False])
def test_uploading_the_pdf_moves_the_date_and_a_plan_can_be_made(client, db, users, loaded, monkeypatch, with_code):
    fake_reader(monkeypatch, with_code)
    before = db.scalar(select(func.count()).select_from(SalesDaily))
    p = preview(client, users["manager"], PDF_FILE.name, PDF_FILE.read_bytes(), "application/pdf")
    assert p.status_code == 200, p.text
    p = p.json()
    lines = printed_lines(PDF_FILE.read_bytes())
    assert (p["kind"], p["read_by_ai"], p["rows_total"]) == ("pdf", True, len(lines))
    # every printed dish, including those whose menu name has Chinese characters, is found; none is guessed wrongly
    assert p["problems"] == 0, [(r["dish"], r["problem"]) for r in p["rows"] if r["problem"]]
    assert p["unmatched"] == [] and (p["date_from"], p["new_days"]) == ("2026-10-22", 1)
    assert p["dishes_sold"] == sum(int(m[6]) for m in lines)

    done = confirm(client, users["manager"], p["draft_id"]).json()
    assert done["today"] == "2026-10-23"  # 22 Oct now has sales, so the app is on Fri 23 Oct
    assert db.scalar(select(func.count()).select_from(SalesDaily)) <= before + len(lines)  # (Honeydew twice merges without a code)
    if with_code:
        from app.modules.catalog.models import MenuItem

        saved = {m.code: s.qty for s, m in db.execute(select(SalesDaily, MenuItem).join(MenuItem, MenuItem.id == SalesDaily.menu_item_id)
                                                      .where(SalesDaily.date == date(2026, 10, 22)))}
        assert saved == {m[4]: int(m[6]) for m in lines}  # every dish landed on the right menu item with the right quantity
    ctx = client.get("/api/planning/context", headers=as_user(users["staff"])).json()
    assert ctx["today"] == "2026-10-23"

    plan = make_plan(client, users, 3)
    assert plan["today"] == "2026-10-23" and plan["forecast"]["days"][0]["is_today"]
    assert plan["forecast"]["history"][-2]["date"] == "2026-10-22" and plan["forecast"]["history"][-2]["total"] > 200
    assert plan["orders"]


def test_the_csv_version_does_the_same_without_the_ai(client, users, loaded):
    p = preview(client, users["manager"], CSV_FILE.name, CSV_FILE.read_bytes()).json()
    assert p["kind"] == "csv" and p["problems"] == 0 and p["unmatched"] == []
    assert confirm(client, users["manager"], p["draft_id"]).json()["today"] == "2026-10-23"


def test_an_english_only_dish_name_is_not_guessed_when_two_dishes_share_it(client, db, users, loaded, monkeypatch):
    """Two dishes that are the same once the Chinese is dropped must stay unmatched, unless a code says which."""
    from app.modules.catalog.models import MenuItem

    for code, name in (("T1", "Test Tea 甲"), ("T2", "Test Tea 乙")):
        db.add(MenuItem(tenant_id=1, code=code, name=name, category="DRINKS", price_rm=3.0, active=True))
    db.commit()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    monkeypatch.setattr(llm, "complete_json_with_pdf", lambda *a, **k: {
        "rows": [{"date": "2026-10-22", "dish": "Test Tea", "qty": 2, "amount": 6.0},
                 {"date": "2026-10-22", "dish": "T2 Test Tea", "qty": 1, "amount": 3.0},
                 {"date": "2026-10-22", "dish": "White rice", "qty": 1, "amount": 1.2}], "notes": ""})
    p = preview(client, users["manager"], "r.pdf", b"%PDF-1.4 x", "application/pdf").json()
    assert (p["rows_ok"], p["problems"]) == (2, 1) and p["unmatched"] == [{"dish": "Test Tea", "rows": 1}]
