"""Small input normalisers shared by controllers and services."""
import re

STUDENT_CODE_PATTERN = re.compile(r"NIT-STU-\d{4}-\d{6}", re.IGNORECASE)


def normalise_phone(raw: str) -> str | None:
    """'98765 43210' / '098765-43210' / '+91 98765 43210' -> '+919876543210'. None if not a phone number."""
    digits = re.sub(r"[\s\-().]", "", raw)
    if digits.startswith("+"):
        return digits if re.fullmatch(r"\+\d{10,15}", digits) else None
    digits = digits.lstrip("0")
    if re.fullmatch(r"\d{10}", digits):
        return "+91" + digits
    if re.fullmatch(r"91\d{10}", digits):
        return "+" + digits
    return None


def is_student_code(value: str) -> bool:
    """A Student ID such as NIT-STU-2026-004182 (any case)."""
    return STUDENT_CODE_PATTERN.fullmatch(value.strip()) is not None
