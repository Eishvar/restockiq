"""Phone formatting shared by supplier validation and external contact links."""
import re


def international_number(raw: str | None) -> str | None:
    """Return international digits, defaulting national numbers to Malaysia."""
    value = (raw or "").strip()
    if not value or not re.fullmatch(r"\+?[0-9\s().-]+", value):
        return None
    digits = re.sub(r"[^0-9]", "", value)
    if not value.startswith("+") and digits.startswith("00"):
        digits = digits[2:]
    elif not value.startswith("+") and digits.startswith("0"):
        if not 9 <= len(digits) <= 11:
            return None
        digits = "60" + digits[1:]
    # The written form +60 (0)12 ... includes a trunk zero that must be omitted.
    if digits.startswith("600"):
        digits = "60" + digits[3:]
    if digits.startswith("60") and not 10 <= len(digits) <= 12:
        return None
    return digits if re.fullmatch(r"[1-9][0-9]{7,14}", digits) else None
