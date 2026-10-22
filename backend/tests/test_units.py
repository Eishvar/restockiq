import pytest

from app.core.units import format_packs, format_qty, to_base


@pytest.mark.parametrize(
    "qty, uom, expected",
    [
        (2400, "g", "2.4 kg"),
        (850, "g", "850 g"),
        (1000, "g", "1 kg"),
        (12500, "g", "12.5 kg"),
        (1500, "ml", "1.5 L"),
        (250, "ml", "250 ml"),
        (38, "pcs", "38 pcs"),
        (1, "pcs", "1 pc"),
        (1800, "pcs", "1,800 pcs"),
        (0, "g", "0 g"),
    ],
)
def test_format_qty(qty, uom, expected):
    assert format_qty(qty, uom) == expected


def test_format_packs():
    assert format_packs(3, "CTN (6x2kg)") == "3 CTN (6x2kg)"
    assert format_packs(1.5, "KG") == "1.5 KG"


def test_to_base():
    assert to_base(2, "kg") == 2000
    assert to_base(1.5, "L") == 1500
    assert to_base(38, "pcs") == 38
    assert to_base(3, "pack", pack_size_base=12000) == 36000


def test_to_base_errors():
    with pytest.raises(ValueError):
        to_base(1, "bucket")
    with pytest.raises(ValueError):
        to_base(1, "pack")
