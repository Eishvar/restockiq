"""Quantities are stored in base units (g / ml / pcs). These helpers convert and display them."""

_TO_BASE = {"g": 1.0, "kg": 1000.0, "ml": 1.0, "l": 1000.0, "pcs": 1.0}


def _num(value: float, decimals: int = 2) -> str:
    """1800.0 -> '1,800'; 2.4 -> '2.4'; 2.456 -> '2.46'."""
    text = f"{value:,.{decimals}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def format_qty(qty_base: float, base_uom: str) -> str:
    """2400 g -> '2.4 kg'; 850 g -> '850 g'; 1500 ml -> '1.5 L'; 38 pcs -> '38 pcs'."""
    uom = base_uom.lower()
    if uom == "g":
        return f"{_num(qty_base / 1000)} kg" if abs(qty_base) >= 1000 else f"{_num(qty_base, 1)} g"
    if uom == "ml":
        return f"{_num(qty_base / 1000)} L" if abs(qty_base) >= 1000 else f"{_num(qty_base, 1)} ml"
    if uom == "pcs":
        return f"{_num(qty_base, 1)} {'pc' if qty_base == 1 else 'pcs'}"
    return f"{_num(qty_base)} {base_uom}"


def format_packs(packs: float, pack_uom: str) -> str:
    """3, 'CTN (6x2kg)' -> '3 CTN (6x2kg)'. The pack description already says what is inside."""
    return f"{_num(packs)} {pack_uom}"


def to_base(qty: float, unit: str, pack_size_base: float | None = None) -> float:
    """Convert a typed quantity to base units. `unit` is g, kg, ml, l, pcs or 'pack'."""
    u = unit.strip().lower()
    if u == "pack":
        if not pack_size_base:
            raise ValueError("pack size is needed to convert packs")
        return qty * pack_size_base
    if u not in _TO_BASE:
        raise ValueError(f"Unknown unit: {unit}")
    return qty * _TO_BASE[u]
