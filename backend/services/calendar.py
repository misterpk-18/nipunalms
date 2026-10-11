"""The Nipuna Academic Calendar (Module 15 §9). The Founder / CEO or Super Admin set company holidays; branch closures are
proposed by the Branch Manager and approved by the Branch Manager (a Branch Manager's own entry is approved as it is
recorded). An approved closure that falls on scheduled classes lists them and asks the branch's Branch Managers to prepare
replacements for the Branch Manager's schedule approval; nothing is cancelled or moved automatically."""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import or_, select

from config.database import db
from config.timezone import IST
from models import Batch, CalendarClosure, ClassSession
from repositories.common import paginate
from services import audit, scope
from services.context import current_user
from services.errors import BusinessRule, Forbidden, NotFound, ValidationError
from services.notifications import notify

CENTRAL = ("FOUNDER_CEO", "SUPER_ADMIN")
BRANCH_PROPOSERS = ("BRANCH_MANAGER", "SUPER_ADMIN")
BRANCH_APPROVERS = ("BRANCH_MANAGER", "SUPER_ADMIN")


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
    branch_ids = _calendar_branch_ids()
    if branch_ids is not None:
        stmt = stmt.where(or_(CalendarClosure.branch_id.is_(None), CalendarClosure.branch_id.in_(branch_ids)))
    if filters.get("branch_id"):
        stmt = stmt.where(or_(CalendarClosure.branch_id.is_(None), CalendarClosure.branch_id == filters["branch_id"]))
    if filters.get("status"):
        stmt = stmt.where(CalendarClosure.status == filters["status"])
    if filters.get("from"):
        stmt = stmt.where(CalendarClosure.ends_on >= filters["from"])
    if filters.get("to"):
        stmt = stmt.where(CalendarClosure.starts_on <= filters["to"])
    return paginate(stmt, page, per_page)


def affected_sessions(closure: CalendarClosure) -> list[ClassSession]:
    """Scheduled or live classes inside the closure (at its branch, or anywhere for a company holiday)."""
    start = datetime.combine(closure.starts_on, time.min, tzinfo=IST)
    end = datetime.combine(closure.ends_on + timedelta(days=1), time.min, tzinfo=IST)
    stmt = (select(ClassSession).join(Batch, Batch.batch_id == ClassSession.batch_id)
            .where(ClassSession.state.in_(("Scheduled", "Live")), ClassSession.starts_at >= start, ClassSession.starts_at < end)
            .order_by(ClassSession.starts_at))
    if closure.branch_id is not None:
        stmt = stmt.where(Batch.branch_id == closure.branch_id)
    return list(db.session.execute(stmt).unique().scalars())


def create_closure(data: dict) -> CalendarClosure:
    user = current_user()
    kind, branch_id = data["kind"], data.get("branch_id")
    if data["ends_on"] < data["starts_on"]:
        raise ValidationError("Invalid request data", {"ends_on": ["The closure ends before it starts"]})
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
    if closure.kind != "Branch Closure" or closure.status != "Pending":
        raise BusinessRule(f"This calendar entry is {closure.status}; only a pending branch closure is decided")
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


def _announce(closure: CalendarClosure) -> None:
    """Ask the Branch Managers of each branch with classes inside the closure to prepare replacements."""
    by_branch: dict[int, list[ClassSession]] = {}
    for session in affected_sessions(closure):
        by_branch.setdefault(session.batch.branch_id, []).append(session)
    for branch_id, sessions in by_branch.items():
        notify(category="Calendar", title=f"{closure.title}: {len(sessions)} class(es) need a replacement",
               body="Prepare replacements for the Branch Manager's schedule approval: "
                    + ", ".join(f"{s.session_code} ({s.starts_at.astimezone(IST):%d %b %H:%M})" for s in sessions[:10]),
               link="/branch/schedule", role_code="BRANCH_MANAGER", branch_id=branch_id,
               event_key=f"closure-affects:{closure.closure_id}:{branch_id}", action_required=True)
