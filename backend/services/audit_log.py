"""Audit log viewer (Super Admin / Founder): filter the append-only history by actor, entity, action, branch and date.

Entries are written by services/audit.py; nothing here changes them.
"""
from datetime import date, datetime, time, timedelta

from config.timezone import IST
from repositories import audit_log as audit_repo
from repositories.common import paginate_rows


def ist_day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=IST)


def list_entries(filters: dict, page: int, per_page: int):
    """Filters `from` / `to` are IST dates, both inclusive."""
    filters = dict(filters)
    if filters.get("from"):
        filters["occurred_from"] = ist_day_start(filters["from"])
    if filters.get("to"):
        filters["occurred_before"] = ist_day_start(filters["to"] + timedelta(days=1))
    return paginate_rows(audit_repo.list_stmt(filters), page, per_page)


def facets() -> dict:
    return audit_repo.facets()
