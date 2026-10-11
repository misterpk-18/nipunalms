"""Downloads of report tables (UX phase U15). CSV only: it opens in Excel and needs no library (no spreadsheet package is in
requirements.txt, so ".xlsx" is not offered).

A cell that starts with = + - or @ would be read as a formula by a spreadsheet; such text gets a leading apostrophe so a name or a
note someone typed can never run as one.
"""
import csv
import io
from datetime import date, datetime

FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    # Numbers keep their minus sign; only text that is not a plain number is guarded
    if text.startswith(FORMULA_STARTS) and not _is_number(text):
        return "'" + text
    return text


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


def to_csv(headers: list[str], rows: list[list]) -> bytes:
    """UTF-8 with a byte-order mark, so Excel reads Telugu and other non-English names correctly."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow([safe_cell(h) for h in headers])
    for row in rows:
        writer.writerow([safe_cell(cell) for cell in row])
    return b"\xef\xbb\xbf" + out.getvalue().encode("utf-8")
