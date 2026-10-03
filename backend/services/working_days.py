"""Working days (Module 15 §9, Modules 19–21 review and alert targets): a day counts when its weekday is in the
`working_weekdays` setting and no approved closure covers it — a company holiday, or a closure at the given branch.
Nothing is assumed closed (not Sundays, weekends or bank holidays) unless the calendar or the setting says so."""
from datetime import date, timedelta

from sqlalchemy import or_, select

from config.database import db
from models import CalendarClosure
from repositories import settings as settings_repo

MAX_SCAN_DAYS = 400  # a target never searches further than this for working days


def _weekdays() -> set[int]:
    configured = settings_repo.get("working_weekdays", [1, 2, 3, 4, 5, 6, 7])
    return set(configured) or {1, 2, 3, 4, 5, 6, 7}


def closed_days(start: date, end: date, branch_id: int | None) -> set[date]:
    """Dates between start and end (inclusive) covered by an approved company holiday or a closure at this branch."""
    stmt = select(CalendarClosure.starts_on, CalendarClosure.ends_on).where(
        CalendarClosure.status == "Approved", CalendarClosure.starts_on <= end, CalendarClosure.ends_on >= start,
        or_(CalendarClosure.branch_id.is_(None), CalendarClosure.branch_id == branch_id) if branch_id is not None
        else CalendarClosure.branch_id.is_(None),
    )
    days: set[date] = set()
    for first, last in db.session.execute(stmt).all():
        day = max(first, start)
        while day <= min(last, end):
            days.add(day)
            day += timedelta(days=1)
    return days


def is_working_day(day: date, branch_id: int | None = None) -> bool:
    return day.isoweekday() in _weekdays() and day not in closed_days(day, day, branch_id)


def add_working_days(start: date, count: int, branch_id: int | None = None) -> date:
    """The date `count` working days after `start` (start itself is day 0). count=0 gives start, or the next working day if
    start is not one."""
    weekdays = _weekdays()
    closed = closed_days(start, start + timedelta(days=MAX_SCAN_DAYS), branch_id)
    day, remaining = start, count
    while day.isoweekday() not in weekdays or day in closed:
        day += timedelta(days=1)
    while remaining > 0:
        day += timedelta(days=1)
        if day.isoweekday() in weekdays and day not in closed:
            remaining -= 1
        if (day - start).days > MAX_SCAN_DAYS:
            break
    return day


def working_days_between(start: date, end: date, branch_id: int | None = None) -> int:
    """Working days after start up to and including end (0 when end <= start)."""
    if end <= start:
        return 0
    weekdays, closed = _weekdays(), closed_days(start, end, branch_id)
    return sum(1 for n in range(1, (end - start).days + 1)
               if (d := start + timedelta(days=n)).isoweekday() in weekdays and d not in closed)
