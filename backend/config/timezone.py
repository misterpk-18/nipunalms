"""Business time: class times and business dates are IST (Asia/Kolkata, UTC+05:30, no daylight saving)."""
from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def today_ist() -> date:
    return datetime.now(IST).date()
