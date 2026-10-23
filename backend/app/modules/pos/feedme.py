"""SIMULATED FeedMe export. No connection to the real FeedMe system exists.

FeedMe's real export layout is not known to us, so this module invents a plausible CSV and generates its
rows from the synthetic data in data/. It stands in for "the till" so the whole journey can be shown:
export from the POS -> upload to RestockIQ -> the forecast learns from the new days.

Days up to the end of data/daily_sales.csv come from that file; later days are generated from the recent
same-weekday sales (deterministic per date, so exporting twice gives the same file).
"""
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

# Invented column names, in the style of a POS "daily item sales" report.
COLUMNS = ["Date", "Outlet", "Item Code", "Item Name", "Category", "Qty Sold", "Unit Price (RM)", "Net Sales (RM)"]
OUTLET = "Main outlet (simulated)"


@lru_cache(maxsize=2)
def _load(data_dir: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = Path(data_dir)
    sales = pd.read_csv(base / "daily_sales.csv", parse_dates=["date"])
    menu = pd.read_csv(base / "menu_items.csv")
    return sales, menu


def last_history_date(data_dir: Path) -> date:
    return _load(str(data_dir))[0]["date"].max().date()


def _generated_day(day: date, grid: pd.DataFrame, price: pd.Series) -> pd.DataFrame:
    """One synthetic day: the average of the last four same weekdays, with a small repeatable wobble."""
    same_weekday = [pd.Timestamp(day - timedelta(days=7 * k)) for k in range(1, 5)]
    avg = grid.reindex(same_weekday).fillna(0).mean()
    wobble = np.random.default_rng(day.toordinal()).uniform(0.85, 1.15, size=len(avg))
    qty = np.rint(avg.to_numpy() * wobble).astype(int)
    out = pd.DataFrame({"item_id": avg.index, "qty": qty})
    out = out[out.qty > 0]
    out["date"] = pd.Timestamp(day)
    out["unit_price_rm"] = out.item_id.map(price)
    out["net_sales_rm"] = (out.qty * out.unit_price_rm).round(2)
    return out


def export_rows(data_dir: Path, start: date, end: date) -> pd.DataFrame:
    """The simulated POS report for start..end (inclusive), in FeedMe-style columns, sorted by date and code."""
    sales, menu = _load(str(data_dir))
    meta = menu.set_index("item_id")
    price = meta["price_rm"]
    history_end = sales["date"].max().date()

    parts = [sales[(sales.date >= pd.Timestamp(start)) & (sales.date <= pd.Timestamp(end))][
        ["date", "item_id", "qty", "unit_price_rm", "net_sales_rm"]
    ]]
    if end > history_end:
        # Generated days lean on the days before them, so always generate from the day after the history.
        grid = sales.pivot_table(index="date", columns="item_id", values="qty", aggfunc="sum").fillna(0)
        day = history_end + timedelta(days=1)
        while day <= end:
            made = _generated_day(day, grid, price)
            if day >= start:
                parts.append(made[["date", "item_id", "qty", "unit_price_rm", "net_sales_rm"]])
            grid.loc[pd.Timestamp(day)] = made.set_index("item_id").qty.reindex(grid.columns).fillna(0)
            day += timedelta(days=1)

    df = pd.concat(parts, ignore_index=True).sort_values(["date", "item_id"])
    return pd.DataFrame(
        {
            "Date": df.date.dt.strftime("%Y-%m-%d"),
            "Outlet": OUTLET,
            "Item Code": df.item_id,
            "Item Name": df.item_id.map(meta["name"]),
            "Category": df.item_id.map(meta["category"]),
            "Qty Sold": df.qty.astype(int),
            "Unit Price (RM)": df.unit_price_rm.map("{:.2f}".format),
            "Net Sales (RM)": df.net_sales_rm.map("{:.2f}".format),
        },
        columns=COLUMNS,
    ).reset_index(drop=True)


def to_csv(df: pd.DataFrame) -> str:
    return df.to_csv(index=False)
