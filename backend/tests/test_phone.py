import pytest

from app.core.phone import international_number
from app.modules.planning.whatsapp import call_url, whatsapp_url


@pytest.mark.parametrize(("raw", "expected"), [
    ("012-345 6789", "60123456789"),
    ("04 123 4567", "6041234567"),
    ("+60 (0)12 345 6789", "60123456789"),
    ("0060 12 345 6789", "60123456789"),
    ("60123456789", "60123456789"),
    ("+65 9123 4567", "6591234567"),
    ("0033 6 12 34 56 78", "33612345678"),
    ("  +44 (20) 7946 0958  ", "442079460958"),
])
def test_international_phone_format(raw, expected):
    assert international_number(raw) == expected
    assert call_url(expected) == f"tel:+{expected}"
    assert whatsapp_url(expected, "Order & delivery\n10/12") == (
        f"https://wa.me/{expected}?text=Order%20%26%20delivery%0A10%2F12"
    )


@pytest.mark.parametrize("raw", [None, "", "   ", "call me", "abc0123456789", "+123",
                                      "0123456", "0000000000", "+0123456789", "1" * 16])
def test_invalid_phone_has_no_contact_link(raw):
    number = international_number(raw)
    assert number is None
    assert call_url(number) is None
    assert whatsapp_url(number, "Order") is None
