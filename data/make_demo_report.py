"""Make the pre-made sales report for ONE extra day, to upload during the demo.

The app's sales end on 2026-10-21, so the app's date is Thu 22 Oct 2026. This script writes what a till would print
for 22 Oct, as a PDF (and the same lines as a CSV, in case the PDF reader is not available):

    demo_reports/sales_report_2026-10-22.pdf
    demo_reports/sales_report_2026-10-22.csv

Nothing in daily_sales.csv or any other data file changes. The numbers are synthetic: drawn with generate.py's demand
rules (weekday, semester, growth) and their own fixed seed, so running this again gives the same files.
Uploading the file on the Sales data page moves the app's date to Fri 23 Oct, and a new plan can then be generated.

Run: python make_demo_report.py            (or: python make_demo_report.py 2026-10-23 for another day)
"""
import csv
import sys
from datetime import date
from pathlib import Path

import numpy as np

import generate as g  # only for the demand rules; importing it writes nothing

HERE = Path(__file__).parent
OUT = HERE / "demo_reports"
LINES_PER_PAGE = 46


def make_day(day: date) -> list[dict]:
    """One row per dish sold on `day`. Same formula as generate.py, own seed."""
    rng = np.random.default_rng(int(day.strftime("%Y%m%d")))
    menu = list(csv.DictReader(open(HERE / "menu_profile.csv", encoding="utf-8")))
    base = g.BASE_ITEMS_PER_DAY * g.day_factor(day) * rng.lognormal(0, 0.07)
    rows = []
    for m in menu:
        if m["launch_date"] and day < g.D(m["launch_date"]):
            continue
        mu = base * float(m["share"]) * g.DOW.get(m["category"], g.DOW["default"])[day.weekday()]
        qty = int(rng.negative_binomial(g.DISPERSION, g.DISPERSION / (g.DISPERSION + mu))) if mu > 0 else 0
        if qty:
            price = float(m["price_rm"])
            rows.append({"code": m["item_id"], "name": m["name"], "qty": qty, "amount": round(qty * price, 2)})
    return rows


def latin(text: str) -> str:
    """The PDF uses a standard font, which cannot print Chinese: keep the English part of a dish name."""
    return " ".join("".join(c for c in text if ord(c) < 128).split())


# ---------- a tiny PDF writer: text only, Helvetica, several pages ----------
def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_bytes(pages: list[list[tuple[int, str]]]) -> bytes:
    """pages = lists of (font size, text) lines. Returns the bytes of a PDF with real, selectable text."""
    objects: list[bytes] = []

    def add(body: str) -> int:
        objects.append(body.encode("latin-1"))
        return len(objects)

    add("<< /Type /Catalog /Pages 2 0 R >>")  # 1
    add("")  # 2: filled in once the page numbers are known
    add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")  # 3
    add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")  # 4
    page_ids = []
    for lines in pages:
        y, ops = 800, []
        for size, text in lines:
            font = "F2" if size > 10 else "F1"
            ops.append(f"BT /{font} {size} Tf 50 {y} Td ({_escape(text)}) Tj ET")
            y -= size + 5
        stream = "\n".join(ops)
        content = add(f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream")
        page_ids.append(add(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {content} 0 R "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>"))
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in page_ids)}] /Count {len(page_ids)} >>".encode("latin-1")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def report_lines(day: date, rows: list[dict]) -> list[str]:
    shown = day.strftime("%d/%m/%Y")  # day first, the way Malaysian tills print it
    # The code is printed in the item column, because two dishes (Honeydew juice and Honeydew) look the same without Chinese.
    return [f"{shown}   {r['code']} {latin(r['name'])}   {r['qty']}   RM {r['amount']:.2f}" for r in rows]


def build_pdf(day: date, rows: list[dict]) -> bytes:
    body = report_lines(day, rows)
    chunks = [body[i : i + LINES_PER_PAGE] for i in range(0, len(body), LINES_PER_PAGE)]
    pages = []
    for n, chunk in enumerate(chunks, start=1):
        head = [(14, "Campus Kopitiam - Daily Sales Report"),
                (10, f"Sales date: {day.strftime('%d/%m/%Y')}    Page {n} of {len(chunks)}"),
                (10, "Demo helper: simulated report with synthetic data. Not a real till and not a connection to one."),
                (10, ""),
                (10, "Date         Item   Qty Sold   Net Sales")]
        foot = []
        if n == len(chunks):
            foot = [(10, ""), (10, f"Total items sold: {sum(r['qty'] for r in rows)}    "
                                   f"Total net sales: RM {sum(r['amount'] for r in rows):,.2f}")]
        pages.append(head + [(10, line) for line in chunk] + foot)
    return pdf_bytes(pages)


def main() -> None:
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2026, 10, 22)
    rows = make_day(day)
    OUT.mkdir(exist_ok=True)
    (OUT / f"sales_report_{day}.pdf").write_bytes(build_pdf(day, rows))
    with open(OUT / f"sales_report_{day}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Item Code", "Item Name", "Qty Sold", "Net Sales (RM)"])
        w.writerows([day.isoformat(), r["code"], r["name"], r["qty"], f"{r['amount']:.2f}"] for r in rows)
    print(f"{day:%a %d %b %Y}: {len(rows)} dishes, {sum(r['qty'] for r in rows)} items, RM {sum(r['amount'] for r in rows):,.2f}")


if __name__ == "__main__":
    main()
