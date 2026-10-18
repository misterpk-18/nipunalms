"""The Nipuna Academic Calendar (Module 15 §9). The Founder / CEO or Super Admin set company holidays; branch closures are
proposed by the Branch Manager and approved by the Branch Manager (a Branch Manager's own entry is approved as it is
recorded). An approved closure that falls on scheduled classes lists them and asks the branch's Branch Managers to prepare
replacements for the Branch Manager's schedule approval; nothing is cancelled or moved automatically."""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import case, or_, select

from config.database import db
from config.timezone import IST, today_ist
from models import Batch, CalendarClosure, ClassSession
from repositories.common import paginate
from services import audit, scope
from services.context import current_user
from services.errors import BusinessRule, Forbidden, NotFound, ValidationError
from services.notifications import notify

CENTRAL = ("FOUNDER_CEO", "SUPER_ADMIN")
BRANCH_PROPOSERS = ("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
BRANCH_APPROVERS = ("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _calendar_branch_ids() -> set[int] | None:
    """Branches whose closures the user sees: those they run or work at (any role); None = all."""
    branch_ids = scope.visible_branch_ids()
    if branch_ids is None:
        return None
    return branch_ids | {s.branch_id for s in current_user().scopes if s.branch_id is not None}


def _get(closure_id: int) -> CalendarClosure:
    closure = db.session.get(CalendarClosure, closure_id)
    branch_ids = _calendar_branch_ids()
    if closure is None or (closure.branch_id is not None and branch_ids is not None and closure.branch_id not in branch_ids):
        raise NotFound("Calendar entry not found")
    return closure


def get_closure(closure_id: int) -> tuple[CalendarClosure, list[ClassSession]]:
    closure = _get(closure_id)
    return closure, affected_sessions(closure)


def list_closures(filters: dict, page: int, per_page: int):
    """Company holidays and the closures of the branches the user works at, newest first."""
    stmt = select(CalendarClosure).order_by(CalendarClosure.starts_on.desc(), CalendarClosure.closure_id.desc())
    if filters.get("sort") == "upcoming":
        # What is still ahead (or going on) first, soonest first; then what is over, latest first
        today = today_ist()
        stmt = stmt.order_by(None).order_by(case((CalendarClosure.ends_on >= today, 0), else_=1),
                                            case((CalendarClosure.ends_on >= today, CalendarClosure.starts_on)).asc().nulls_last(),
                                            CalendarClosure.starts_on.desc(), CalendarClosure.closure_id.desc())
    branch_ids = _calendar_branch_ids()
    if branch_ids is not None:
        stmt = stmt.where(or_(CalendarClosure.branch_id.is_(None), CalendarClosure.branch_id.in_(branch_ids)))
    if filters.get("branch_id"):
        stmt = stmt.where(or_(CalendarClosure.branch_id.is_(None), CalendarClosure.branch_id == filters["branch_id"]))
    if filters.get("status") == "Cancelled":
        stmt = stmt.where(CalendarClosure.cancelled_at.is_not(None))
    elif filters.get("status"):
        stmt = stmt.where(CalendarClosure.status == filters["status"], CalendarClosure.cancelled_at.is_(None))
    if filters.get("from"):
        stmt = stmt.where(CalendarClosure.ends_on >= filters["from"])
    if filters.get("to"):
        stmt = stmt.where(CalendarClosure.starts_on <= filters["to"])
    return paginate(stmt, page, per_page)


def affected_sessions(closure: CalendarClosure) -> list[ClassSession]:
    """Scheduled or live classes inside the closure (at its branch, or anywhere for a company holiday)."""
    return _classes_between(closure.starts_on, closure.ends_on, closure.branch_id)


def _classes_between(starts_on: date, ends_on: date, branch_id: int | None) -> list[ClassSession]:
    """Scheduled or live classes whose day falls in the range, at the branch (any branch for a company holiday)."""
    start = datetime.combine(starts_on, time.min, tzinfo=IST)
    end = datetime.combine(ends_on + timedelta(days=1), time.min, tzinfo=IST)
    stmt = (select(ClassSession).join(Batch, Batch.batch_id == ClassSession.batch_id)
            .where(ClassSession.state.in_(("Scheduled", "Live")), ClassSession.starts_at >= start, ClassSession.starts_at < end)
            .order_by(ClassSession.starts_at))
    if branch_id is not None:
        stmt = stmt.where(Batch.branch_id == branch_id)
    return list(db.session.execute(stmt).unique().scalars())


MAX_DAYS = 62  # the database refuses a longer entry (calendar_closures_dates)


def _check_dates(starts_on: date, ends_on: date) -> None:
    if ends_on < starts_on:
        raise ValidationError("Invalid request data", {"ends_on": ["The closure ends before it starts"]})
    if (ends_on - starts_on).days > MAX_DAYS:
        raise ValidationError("Invalid request data", {"ends_on": [f"A closure can last at most {MAX_DAYS + 1} days; add a second entry for longer"]})


def create_closure(data: dict) -> CalendarClosure:
    user = current_user()
    kind, branch_id = data["kind"], data.get("branch_id")
    _check_dates(data["starts_on"], data["ends_on"])
    if kind == "Company Holiday":
        if branch_id is not None:
            raise ValidationError("Invalid request data", {"branch_id": ["A company holiday applies to every branch"]})
        if not user.has_role(*CENTRAL):
            raise Forbidden("Company holidays are set by the Founder / CEO or Super Admin")
        approved_now = True
    else:
        if branch_id is None:
            raise ValidationError("Invalid request data", {"branch_id": ["Say which branch is closed"]})
        scope.require_branch(branch_id)
        if not user.has_role(*BRANCH_PROPOSERS, branch_id=branch_id):
            raise Forbidden("Branch closures are proposed by the branch's Branch Manager")
        approved_now = user.has_role(*BRANCH_APPROVERS, branch_id=branch_id)
    closure = CalendarClosure(kind=kind, branch_id=branch_id, starts_on=data["starts_on"], ends_on=data["ends_on"], title=data["title"],
                              reason=data.get("reason"), requested_by=user.user_id)
    if approved_now:
        closure.status, closure.decided_by, closure.decided_at = "Approved", user.user_id, _now()
    db.session.add(closure)
    db.session.flush()
    audit.record("CALENDAR_CLOSURE_" + ("APPROVED" if approved_now else "PROPOSED"), "calendar_closure", closure.closure_id,
                 new={"kind": kind, "starts_on": closure.starts_on.isoformat(), "ends_on": closure.ends_on.isoformat()},
                 reason=closure.reason, branch_id=branch_id)
    if approved_now:
        _announce(closure)
    else:
        notify(category="Calendar", title=f"Branch closure to approve: {closure.title}",
               body=f"{closure.starts_on:%d %b} – {closure.ends_on:%d %b %Y}. {closure.reason or ''}".strip(),
               link="/branch/schedule", role_code="BRANCH_MANAGER", branch_id=branch_id,
               event_key=f"closure-proposed:{closure.closure_id}", action_required=True)
    return closure


def decide_closure(closure_id: int, decision: str, note: str | None) -> CalendarClosure:
    closure = _get(closure_id)
    if closure.kind != "Branch Closure" or closure.status != "Pending" or closure.is_cancelled:
        raise BusinessRule(f"This calendar entry is {'Cancelled' if closure.is_cancelled else closure.status}; only a pending branch closure is decided")
    if not current_user().has_role(*BRANCH_APPROVERS, branch_id=closure.branch_id):
        raise Forbidden("The Branch Manager approves branch closures")
    if decision == "Rejected" and not note:
        raise ValidationError("Invalid request data", {"note": ["Give the reason for rejecting the closure"]})
    closure.status, closure.decided_by, closure.decided_at, closure.decision_note = decision, current_user().user_id, _now(), note
    db.session.flush()
    audit.record(f"CALENDAR_CLOSURE_{decision.upper()}", "calendar_closure", closure.closure_id, reason=note, branch_id=closure.branch_id)
    if decision == "Approved":
        _announce(closure)
    return closure


def _announce(closure: CalendarClosure, sessions: list[ClassSession] | None = None, key: str = "") -> None:
    """Ask the Branch Managers of each branch with classes inside the closure (or the given classes) to prepare replacements."""
    by_branch: dict[int, list[ClassSession]] = {}
    for session in affected_sessions(closure) if sessions is None else sessions:
        by_branch.setdefault(session.batch.branch_id, []).append(session)
    for branch_id, sessions in by_branch.items():
        notify(category="Calendar", title=f"{closure.title}: {len(sessions)} class(es) need a replacement",
               body="Prepare replacements for the Branch Manager's schedule approval: "
                    + ", ".join(f"{s.session_code} ({s.starts_at.astimezone(IST):%d %b %H:%M})" for s in sessions[:10]),
               link="/branch/schedule", role_code="BRANCH_MANAGER", branch_id=branch_id,
               event_key=f"closure-affects:{closure.closure_id}:{branch_id}" + (f":{key}" if key else ""), action_required=True)


# ---------------------------------------------------------------- edit and cancel (UX phase U17)

def _manage(closure: CalendarClosure) -> None:
    """Who may change an entry: the people who may add that kind (central staff for a holiday; the branch's manager or a Super Admin)."""
    user = current_user()
    if closure.kind == "Company Holiday":
        if not user.has_role(*CENTRAL):
            raise Forbidden("Company holidays are changed by the Founder / CEO or Super Admin")
    elif not user.has_role(*BRANCH_PROPOSERS, branch_id=closure.branch_id):
        raise Forbidden("Branch closures are changed by the branch's Branch Manager or a Super Admin")
    if closure.is_cancelled or closure.status == "Rejected":
        raise BusinessRule(f"This entry is {'cancelled' if closure.is_cancelled else 'rejected'} and can't be changed")
    if closure.ends_on < today_ist():
        raise BusinessRule("This closure is already over and can't be changed")


def _impact(entry: dict, classes: list[ClassSession], **extra) -> dict:
    return {**entry, "affected_count": len(classes),
            "affected_sessions": [{**s.to_summary(), "batch": s.batch.to_summary()} for s in classes], **extra}


def update_closure(closure_id: int, changes: dict, dry_run: bool = False) -> dict:
    """Change the title, reason or dates of an entry that is not over. The reply lists the classes inside the new dates
    (`affected_sessions`), how many of them are new to the closure and how many it no longer covers. `dry_run` answers the same
    without saving, so the screen can show the impact before the person confirms."""
    closure = _get(closure_id)
    _manage(closure)
    starts_on, ends_on = changes.get("starts_on", closure.starts_on), changes.get("ends_on", closure.ends_on)
    _check_dates(starts_on, ends_on)
    before = _classes_between(closure.starts_on, closure.ends_on, closure.branch_id)
    after = _classes_between(starts_on, ends_on, closure.branch_id)
    before_ids = {s.session_id for s in before}
    after_ids = {s.session_id for s in after}
    newly = [s for s in after if s.session_id not in before_ids]
    extra = {"newly_affected_count": len(newly), "freed_count": len(before_ids - after_ids)}

    changed = {k: v for k, v in changes.items() if getattr(closure, k) != v}
    if dry_run or not changed:
        return _impact({**closure.to_dict(), **{k: v for k, v in changed.items()}}, after, **extra, saved=False)

    old = {k: getattr(closure, k) for k in changed}
    for field, value in changed.items():
        setattr(closure, field, value)
    db.session.flush()
    audit.record("CALENDAR_CLOSURE_UPDATED", "calendar_closure", closure.closure_id, old=old, new=changed, branch_id=closure.branch_id)
    if closure.status == "Approved" and newly:
        _announce(closure, newly, f"edit-{_now():%Y%m%d%H%M%S}")
    return _impact(closure.to_dict(), after, **extra, saved=True)


def cancel_closure(closure_id: int, reason: str, dry_run: bool = False) -> dict:
    """Cancel an entry that is not over. The classes inside its dates (`affected_sessions`) are no longer held back: they run
    as scheduled, and the Branch Managers are told. `dry_run` answers without cancelling."""
    closure = _get(closure_id)
    _manage(closure)
    classes = affected_sessions(closure)
    if dry_run:
        return _impact(closure.to_dict(), classes, saved=False)
    was_in_force = closure.status == "Approved"
    previous = closure.status
    closure.cancelled_by, closure.cancelled_at, closure.cancel_reason = current_user().user_id, _now(), reason
    db.session.flush()
    audit.record("CALENDAR_CLOSURE_CANCELLED", "calendar_closure", closure.closure_id, old={"status": previous}, new={"status": "Cancelled"},
                 reason=reason, branch_id=closure.branch_id)
    if was_in_force:
        by_branch: dict[int, list[ClassSession]] = {}
        for session in classes:
            by_branch.setdefault(session.batch.branch_id, []).append(session)
        for branch_id, sessions in by_branch.items():
            notify(category="Calendar", title=f"{closure.title} was cancelled: {len(sessions)} class(es) run as scheduled",
                   body="These classes are no longer closed: " + ", ".join(f"{s.session_code} ({s.starts_at.astimezone(IST):%d %b %H:%M})" for s in sessions[:10]),
                   link="/branch/schedule", role_code="BRANCH_MANAGER", branch_id=branch_id, event_key=f"closure-cancelled:{closure.closure_id}:{branch_id}")
    return _impact(closure.to_dict(), classes, saved=True)
