"""Live-class operations (Module 15 §10-11, §15; Module 16 §4-7, §10): hosts, backups and guests, compromised-link incidents,
Meet participation evidence, delayed starts and disruptions, missing class logs, substitute / assistant cover, shared classes,
and the Meet operations view.

Meet participation is evidence for review only: it never marks attendance. A delayed start is a provider or institute
problem, not a student absence: at 5 minutes the students are told, at 15 a disruption is recorded and the Branch Manager and
Branch Manager are alerted to agree a recovery plan; the undelivered minutes are recorded when it is resolved.
"""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select

from config.database import db
from config.timezone import IST, today_ist
from models import (
    AttendanceRecord, Batch, ClassSession, JobRun, MeetIncident, MeetParticipation, Recording, RecordingException, SessionChange,
    SessionCoverRequest, SessionDisruption, SessionPerson, SessionRoster,
)
from repositories import attendance as attendance_repo
from repositories import batches as batches_repo
from repositories import catalog as catalog_repo
from repositories import class_sessions as sessions_repo
from repositories import settings as settings_repo
from repositories import users as users_repo
from repositories.common import paginate
from services import approvals, audit, delivery_access, delivery_notices, meet, scope, working_days
from services.class_sessions import _load_for_change, _notify_students, _require_open, _slot, assert_can_view_session
from services.context import ACADEMIC_ROLES, actor_id, current_user
from services.errors import BusinessRule, Conflict, Forbidden, NotFound, ValidationError

OPEN = ("Scheduled", "Rescheduled")
STAFF_ROLES_FOR_HOSTING = ("TRAINER", "BRANCH_MANAGER")
DELAY_LOOKBACK = timedelta(hours=12)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_confirmer(branch_id: int, requester: int | None = None) -> None:
    approvals.require_decider(branch_id, requester, "Only the Branch Manager of this branch decides this")


def _holds_any(user_id: int, roles: tuple[str, ...]) -> bool:
    return any(user_id in users_repo.user_ids_with_role(role, None) for role in roles)


def _session_people(session_id: int, include_removed: bool = False) -> list[SessionPerson]:
    stmt = select(SessionPerson).where(SessionPerson.session_id == session_id).order_by(SessionPerson.session_person_id)
    if not include_removed:
        stmt = stmt.where(SessionPerson.removed_at.is_(None))
    return list(db.session.execute(stmt).scalars())


def operations_detail(session_id: int) -> dict:
    """Hosts, guests, incidents, disruptions, cover, joined batches and participation of one class (staff only)."""
    session = sessions_repo.get_session(session_id)
    if session is None:
        raise NotFound("Class session not found")
    assert_can_view_session(session)
    if delivery_access.is_student_only():
        raise NotFound("Class session not found")
    rows = lambda model, order: list(db.session.execute(select(model).where(model.session_id == session_id).order_by(order)).scalars())  # noqa: E731
    return {
        "people": [p.to_dict() for p in _session_people(session_id, include_removed=True)],
        "incidents": [i.to_dict() for i in rows(MeetIncident, MeetIncident.reported_at)],
        "disruptions": [d.to_dict() for d in rows(SessionDisruption, SessionDisruption.detected_at)],
        "cover_requests": [c.to_dict() for c in rows(SessionCoverRequest, SessionCoverRequest.requested_at)],
        "rosters": [r.to_dict() for r in rows(SessionRoster, SessionRoster.verified_at)],
        "participation": [p.to_dict() for p in rows(MeetParticipation, MeetParticipation.joined_at)],
        "replacements": [s.to_summary() for s in db.session.execute(select(ClassSession).where(
            ClassSession.replaces_session_id == session_id)).scalars()],
    }


# ---------------------------------------------------------------- hosts, backups and guests (Module 16 §5)

def add_person(session_id: int, data: dict) -> SessionPerson:
    """Name the actual host or the backup (a staff member with a verified identity), or propose a guest for approval."""
    session = _load_for_change(session_id)
    _require_open(session, "changed")
    role = data["role"]
    if role == "Guest":
        if not data.get("guest_name") or not data.get("purpose"):
            raise ValidationError("Name the guest and why", {"guest_name": ["Required"], "purpose": ["Required"]})
        person = SessionPerson(session_id=session_id, role="Guest", guest_name=data["guest_name"], guest_email=data.get("guest_email"),
                               purpose=data["purpose"], student_agreement=data.get("student_agreement"), status="Pending",
                               added_by=actor_id())
    else:
        user_id = data.get("user_id")
        if not user_id or not _holds_any(user_id, STAFF_ROLES_FOR_HOSTING):
            raise ValidationError("Invalid person", {"user_id": ["A staff member with a verified identity"]})
        if role == "Backup" and user_id == session.trainer_user_id:
            raise ValidationError("Invalid backup", {"user_id": ["The backup is someone other than the trainer"]})
        busy = sessions_repo.people_conflict([user_id], session.starts_at, session.ends_at, session.session_id)
        if busy is not None:
            raise BusinessRule(f"They are busy with {busy.session_code} on {_slot(busy.starts_at, busy.ends_at)}")
        for existing in _session_people(session_id):
            if existing.role == role or existing.user_id == user_id:
                existing.removed_at = _now()
        db.session.flush()
        person = SessionPerson(session_id=session_id, role=role, user_id=user_id, added_by=actor_id())
    db.session.add(person)
    db.session.flush()
    audit.record("SESSION_PERSON_ADDED", "class_session", session_id, branch_id=session.batch.branch_id,
                 new={"role": role, "user_id": person.user_id, "guest_name": person.guest_name})
    if role == "Guest":
        delivery_notices.notify_branch_managers(session.batch.branch_id, title=f"Approve a class guest: {session.title}", category="Session",
                                                body=f"{person.guest_name} — {person.purpose}", action_required=True,
                                                event_key=f"session-guest-{person.session_person_id}", link="/branch/class-day")
    else:
        delivery_notices.notify_users([person.user_id], title=f"You are the {role.lower()} for {session.title}", category="Session",
                                      body=_slot(session.starts_at, session.ends_at), event_key=f"session-person-{person.session_person_id}",
                                      link=f"/sessions/{session_id}", branch_id=session.batch.branch_id)
    return person


def decide_guest(person_id: int, decision: str, note: str | None) -> SessionPerson:
    """The Branch Manager approves a class guest, not the person who proposed them. A guest gets no LMS
    content or recording rights."""
    person = db.session.get(SessionPerson, person_id)
    if person is None or person.role != "Guest":
        raise NotFound("Guest not found")
    session = _load_for_change(person.session_id, requester=person.added_by)
    if person.status != "Pending":
        raise BusinessRule(f"The guest is already {person.status}")
    approvals.require_independent(person.added_by, message="The person who proposed the guest cannot approve them", requester=person.added_by)
    person.status, person.decided_by, person.decided_at = decision, actor_id(), _now()
    db.session.flush()
    audit.record("SESSION_GUEST_DECIDED", "class_session", session.session_id, branch_id=session.batch.branch_id, reason=note,
                 new={"guest_name": person.guest_name, "status": decision})
    return person


def remove_person(person_id: int) -> SessionPerson:
    person = db.session.get(SessionPerson, person_id)
    if person is None or person.removed_at is not None:
        raise NotFound("Not found")
    session = _load_for_change(person.session_id)
    person.removed_at = _now()
    db.session.flush()
    audit.record("SESSION_PERSON_REMOVED", "class_session", session.session_id, branch_id=session.batch.branch_id,
                 old={"role": person.role, "user_id": person.user_id, "guest_name": person.guest_name})
    return person


# ---------------------------------------------------------------- compromised links (Module 16 §5)

def report_incident(session_id: int, data: dict) -> MeetIncident:
    """Secure the meeting, alert the manager, replace the link if needed, tell the participants and keep the history."""
    session = _load_for_change(session_id, allow_own_trainer=True)
    if session.mode == "Classroom":
        raise BusinessRule("A classroom session has no Meet")
    incident = MeetIncident(session_id=session_id, kind=data["kind"], description=data["description"], actions_taken=data["actions_taken"],
                            reported_by=actor_id(), old_meet_link=session.meet_link)
    if data.get("replace_link") and session.meet_status == "Linked":
        session.meet_link, session.meet_status = None, "Pending Verification"
        session.confirmed_at = session.confirmed_by = None
        incident.link_replaced = True
        db.session.flush()
        meet.record(session, "Link removed", f"{data['kind']}: the link is being replaced")
    db.session.add(incident)
    db.session.flush()
    delivery_notices.notify_branch_managers(session.batch.branch_id, title=f"Meet incident: {session.title}", category="Session",
                                            body=f"{data['kind']} — {data['description']}. Done: {data['actions_taken']}", action_required=True,
                                            event_key=f"meet-incident-{incident.incident_id}", link="/branch/class-day")
    incident.manager_alerted_at = _now()
    if incident.link_replaced:
        body = "The class link was replaced for security. Join from the LMS; do not use or share the old link."
        _notify_students(session, title=f"New class link: {session.title}", body=body, event_key=f"meet-incident-{incident.incident_id}")
        helpers = [p.user_id for p in _session_people(session_id) if p.user_id]
        delivery_notices.notify_users([session.trainer_user_id, *helpers], title=f"New class link: {session.title}", body=body,
                                      event_key=f"meet-incident-{incident.incident_id}", link=f"/sessions/{session_id}",
                                      branch_id=session.batch.branch_id)
        incident.participants_notified_at = _now()
    db.session.flush()
    audit.record("MEET_INCIDENT", "class_session", session_id, branch_id=session.batch.branch_id,
                 new={"kind": incident.kind, "link_replaced": incident.link_replaced})
    return incident


# ---------------------------------------------------------------- Meet participation evidence (Module 16 §7)

def _match(session: ClassSession, email: str | None) -> tuple[int | None, int | None]:
    if not email:
        return None, None
    user = users_repo.get_by_email(email)
    if user is None:
        return None, None
    if user.student_id is None:
        return user.user_id, None
    seats = {e.enrolment_id: e for e in attendance_repo.allocated_enrolments(sessions_repo.session_batch_ids(session.session_id))}
    enrolment = next((e for e in seats.values() if e.student_id == user.student_id), None)
    return (user.user_id, enrolment.enrolment_id) if enrolment else (None, None)


def record_participation(session_id: int, rows: list[dict], source: str) -> list[MeetParticipation]:
    """Join / leave evidence (reconnects are separate rows). Identities matched to a staff member or a seated student by email;
    anything else waits as Unmatched for review. Never attendance."""
    session = _load_for_change(session_id)
    if session.mode == "Classroom":
        raise BusinessRule("A classroom session has no Meet")
    saved = []
    for row in rows:
        user_id, enrolment_id = _match(session, row.get("participant_email"))
        entry = MeetParticipation(session_id=session_id, participant_name=row.get("participant_name"),
                                  participant_email=row.get("participant_email"), joined_at=row["joined_at"], left_at=row.get("left_at"),
                                  source=source, match_status="Matched" if user_id else "Unmatched", matched_user_id=user_id,
                                  matched_enrolment_id=enrolment_id, recorded_by=actor_id())
        db.session.add(entry)
        saved.append(entry)
    db.session.flush()
    return saved


def review_participation(participation_id: int, data: dict) -> MeetParticipation:
    entry = db.session.get(MeetParticipation, participation_id)
    if entry is None:
        raise NotFound("Participation entry not found")
    session = _load_for_change(entry.session_id)
    if data["match_status"] == "Matched":
        user = users_repo.get_by_id(data.get("user_id") or 0)
        if user is None:
            raise ValidationError("Who is it?", {"user_id": ["Name the person"]})
        entry.matched_user_id = user.user_id
        _, entry.matched_enrolment_id = _match(session, user.email)
    entry.match_status, entry.reviewed_by, entry.reviewed_at, entry.review_note = data["match_status"], actor_id(), _now(), data.get("note")
    db.session.flush()
    audit.record("MEET_PARTICIPATION_REVIEWED", "class_session", session.session_id, branch_id=session.batch.branch_id,
                 new={"participation_id": participation_id, "match_status": entry.match_status, "user_id": entry.matched_user_id})
    return entry


def list_unmatched(filters: dict, page: int, per_page: int):
    stmt = (select(MeetParticipation).join(ClassSession, ClassSession.session_id == MeetParticipation.session_id)
            .join(Batch, Batch.batch_id == ClassSession.batch_id).where(MeetParticipation.match_status == "Unmatched")
            .order_by(MeetParticipation.joined_at.desc()))
    branch_ids = scope.visible_branch_ids()
    if branch_ids is not None:
        stmt = stmt.where(Batch.branch_id.in_(branch_ids or {0}))
    if filters.get("branch_id"):
        stmt = stmt.where(Batch.branch_id == filters["branch_id"])
    return paginate(stmt, page, per_page)


# ---------------------------------------------------------------- delayed starts and disruptions (Module 16 §7)

def _alert_disruption(session: ClassSession, disruption: SessionDisruption) -> None:
    delivery_notices.notify_branch_managers(
        session.batch.branch_id, title=f"Class disrupted: {session.title}", category="Session", action_required=True,
        body=f"{session.batch.batch_code} · {disruption.kind}" + (f" ({disruption.delay_minutes} min)" if disruption.delay_minutes else "")
        + ". Agree and communicate a recovery or replacement plan.",
        event_key=f"session-disruption-{disruption.disruption_id}", link="/branch/class-day")


def check_delays(now: datetime | None = None) -> dict:
    """Job: an online or hybrid class not started 5 minutes after its start tells its students; at 15 minutes a disruption is
    recorded and the Branch Manager are alerted (once each per class). The LMS only knows a class started
    when the trainer starts it, so a late classroom class is recorded by hand (`record_disruption`)."""
    now = now or _now()
    notice_after = timedelta(minutes=settings_repo.get_int("session_delay_notice_minutes", 5))
    disruption_after = timedelta(minutes=settings_repo.get_int("session_disruption_minutes", 15))
    late = db.session.execute(select(ClassSession).where(
        ClassSession.state.in_(OPEN), ClassSession.approval_status != "Pending", ClassSession.mode != "Classroom",
        ClassSession.starts_at <= now - notice_after, ClassSession.starts_at >= now - DELAY_LOOKBACK)).scalars().all()
    told = recorded = 0
    for session in late:
        delay = int((now - session.starts_at).total_seconds() // 60)
        if session.delay_notice_at is None and now < session.ends_at:
            session.delay_notice_at = now
            _notify_students(session, title=f"Your class is running late: {session.title}",
                             body="The class has not started yet. Staff are on it; you will be told the next step here.",
                             event_key=f"session-delay-{session.session_id}")
            told += 1
        if now - session.starts_at >= disruption_after and not db.session.execute(select(SessionDisruption.disruption_id).where(
                SessionDisruption.session_id == session.session_id, SessionDisruption.kind == "Delayed start")).first():
            disruption = SessionDisruption(session_id=session.session_id, kind="Delayed start", delay_minutes=delay,
                                           detail="Not started by the disruption threshold (session-delay-check)")
            db.session.add(disruption)
            db.session.flush()
            _alert_disruption(session, disruption)
            recorded += 1
    db.session.flush()
    return {"students_told": told, "disruptions": recorded}


def record_disruption(session_id: int, data: dict) -> SessionDisruption:
    """A trainer or manager records a disruption the job cannot see (a connection failure, a failed start)."""
    session = _load_for_change(session_id, allow_own_trainer=True)
    if session.state == "Cancelled":
        raise BusinessRule("The class is cancelled")
    if data["kind"] == "Delayed start" and db.session.execute(select(SessionDisruption.disruption_id).where(
            SessionDisruption.session_id == session_id, SessionDisruption.kind == "Delayed start")).first():
        raise Conflict("A delayed start is already recorded for this class")
    disruption = SessionDisruption(session_id=session_id, kind=data["kind"], cause=data.get("cause", "Unknown"), detail=data.get("detail"),
                                   delay_minutes=data.get("delay_minutes"), raised_by=actor_id())
    db.session.add(disruption)
    db.session.flush()
    _alert_disruption(session, disruption)
    return disruption


def resolve_disruption(disruption_id: int, data: dict) -> SessionDisruption:
    """The Branch Manager or Branch Manager records the cause, the undelivered minutes and the recovery or replacement plan; the
    students are told the plan."""
    disruption = db.session.get(SessionDisruption, disruption_id)
    if disruption is None:
        raise NotFound("Disruption not found")
    session = _load_for_change(disruption.session_id)
    if disruption.status == "Resolved":
        raise BusinessRule("The disruption is already resolved")
    if data.get("replacement_session_id"):
        replacement = sessions_repo.get_session(data["replacement_session_id"])
        if replacement is None or replacement.replaces_session_id != session.session_id:
            raise ValidationError("Invalid replacement", {"replacement_session_id": ["A replacement class of this session"]})
    disruption.recovery_plan, disruption.undelivered_minutes = data["recovery_plan"], data["undelivered_minutes"]
    disruption.cause = data.get("cause", disruption.cause)
    disruption.replacement_session_id = data.get("replacement_session_id")
    disruption.owner_user_id = data.get("owner_user_id") or actor_id()
    disruption.status, disruption.resolved_by, disruption.resolved_at = "Resolved", actor_id(), _now()
    db.session.flush()
    audit.record("SESSION_DISRUPTION_RESOLVED", "class_session", session.session_id, branch_id=session.batch.branch_id,
                 new={"disruption_id": disruption_id, "undelivered_minutes": disruption.undelivered_minutes, "cause": disruption.cause})
    _notify_students(session, title=f"Recovery plan: {session.title}", body=disruption.recovery_plan,
                     event_key=f"session-disruption-{disruption_id}-plan")
    return disruption


def list_disruptions(filters: dict, page: int, per_page: int):
    stmt = (select(SessionDisruption).join(ClassSession, ClassSession.session_id == SessionDisruption.session_id)
            .join(Batch, Batch.batch_id == ClassSession.batch_id).order_by(SessionDisruption.detected_at.desc()))
    branch_ids = scope.visible_branch_ids()
    if branch_ids is not None:
        stmt = stmt.where(Batch.branch_id.in_(branch_ids or {0}) | Batch.batch_id.in_(scope.trainer_batch_ids() or {0}))
    for key, column in (("status", SessionDisruption.status), ("branch_id", Batch.branch_id), ("batch_id", Batch.batch_id)):
        if filters.get(key):
            stmt = stmt.where(column == filters[key])
    return paginate(stmt, page, per_page)


# ---------------------------------------------------------------- missing class logs (Module 15 §15)

def log_due_on(session: ClassSession) -> date:
    """The end of the class's working day (the next working day when the class fell on a closed day)."""
    return working_days.add_working_days(session.ends_at.astimezone(IST).date(), 0, session.batch.branch_id)


def check_class_logs() -> dict:
    """Job: a class still not logged (not Delivered or Cancelled) after its working day raises a Branch Manager
    review task, once."""
    today = today_ist()
    since = datetime.combine(today - timedelta(days=settings_repo.get_int("class_log_lookback_days", 14)), time.min, tzinfo=IST)
    rows = db.session.execute(select(ClassSession).where(
        ClassSession.state.in_(("Scheduled", "Rescheduled", "Live")), ClassSession.log_overdue_at.is_(None),
        ClassSession.approval_status != "Pending", ClassSession.ends_at >= since,
        ClassSession.ends_at < datetime.combine(today, time.min, tzinfo=IST))).scalars().all()
    flagged = 0
    for session in rows:
        if log_due_on(session) >= today:
            continue
        session.log_overdue_at = _now()
        delivery_notices.notify_users(users_repo.user_ids_with_role("BRANCH_MANAGER", session.batch.branch_id), category="Session",
                                      title=f"Class log missing: {session.title}", action_required=True,
                                      body=f"{session.batch.batch_code} · {_slot(session.starts_at, session.ends_at)} · {session.trainer.full_name}",
                                      event_key=f"class-log-missing-{session.session_id}", link="/branch/schedule",
                                      branch_id=session.batch.branch_id)
        flagged += 1
    db.session.flush()
    return {"flagged": flagged}


# ---------------------------------------------------------------- substitute and assistant cover (Module 15 §11)

def request_cover(session_id: int, data: dict) -> SessionCoverRequest:
    session = _load_for_change(session_id)
    _require_open(session, "covered")
    cover_id = data["cover_user_id"]
    if cover_id == session.trainer_user_id:
        raise ValidationError("Invalid cover", {"cover_user_id": ["That is already the class's trainer"]})
    if not _holds_any(cover_id, ("TRAINER",)):
        raise ValidationError("Invalid cover", {"cover_user_id": ["Cover is given by someone holding the Trainer role"]})
    busy = sessions_repo.people_conflict([cover_id], session.starts_at, session.ends_at, session.session_id)
    if busy is not None:
        raise BusinessRule(f"They are busy with {busy.session_code} on {_slot(busy.starts_at, busy.ends_at)}")
    if db.session.execute(select(SessionCoverRequest.request_id).where(
            SessionCoverRequest.session_id == session_id, SessionCoverRequest.cover_role == data["cover_role"],
            SessionCoverRequest.status.in_(("Pending", "Approved")))).first():
        raise Conflict(f"A {data['cover_role'].lower()} request for this class is already open")
    request = SessionCoverRequest(session_id=session_id, cover_role=data["cover_role"], planned_trainer_user_id=session.trainer_user_id,
                                  cover_user_id=cover_id, reason=data["reason"], scope=data["scope"], handover=data["handover"],
                                  requested_by=actor_id())
    db.session.add(request)
    db.session.flush()
    delivery_notices.notify_users(users_repo.user_ids_with_role("BRANCH_MANAGER", session.batch.branch_id), category="Session",
                                  action_required=True, title=f"Approve {data['cover_role'].lower()} cover: {session.title}",
                                  body=f"{_slot(session.starts_at, session.ends_at)}. {data['reason']}",
                                  event_key=f"cover-request-{request.request_id}", link="/branch/class-day",
                                  branch_id=session.batch.branch_id)
    return request


def _load_cover(request_id: int) -> SessionCoverRequest:
    request = db.session.get(SessionCoverRequest, request_id)
    if request is None:
        raise NotFound("Cover request not found")
    _load_for_change(request.session_id, requester=request.requested_by)
    if request.status not in ("Pending", "Approved"):
        raise BusinessRule(f"The request is already {request.status}")
    return request


def decide_cover(request_id: int, decision: str, note: str | None) -> SessionCoverRequest:
    """The Branch Manager (or Super Admin), not the requester, approves the cover assignment."""
    request = _load_cover(request_id)
    _require_confirmer(request.session.batch.branch_id, request.requested_by)
    if request.approved_at is not None:
        raise BusinessRule("The cover is already approved")
    approvals.require_independent(request.requested_by, message="The requester cannot approve their own cover request",
                                  requester=request.requested_by)
    if decision == "Rejected":
        if not note:
            raise ValidationError("A reason is required", {"note": ["Say why"]})
        request.status, request.decision_note = "Rejected", note
        db.session.flush()
        return request
    request.approved_by, request.approved_at, request.decision_note, request.status = actor_id(), _now(), note, "Approved"
    db.session.flush()
    return _apply_cover_when_ready(request)


def verify_cover(request_id: int, note: str) -> SessionCoverRequest:
    """The Branch Manager (or Super Admin) verifies the cover's competence, scope and handover."""
    request = _load_cover(request_id)
    if not current_user().has_role(*ACADEMIC_ROLES, branch_id=request.session.batch.branch_id):
        raise Forbidden("Only the Branch Manager of this branch, a Super Admin or the Founder verifies cover")
    if request.verified_at is not None:
        raise BusinessRule("The cover is already verified")
    request.verified_by, request.verified_at, request.verification_note = actor_id(), _now(), note
    db.session.flush()
    return _apply_cover_when_ready(request)


def _apply_cover_when_ready(request: SessionCoverRequest) -> SessionCoverRequest:
    """Approved and verified: the substitute takes the class (or the assistant joins it) and its students are told."""
    if request.approved_at is None or request.verified_at is None:
        return request
    session = sessions_repo.get_session_for_update(request.session_id)
    _require_open(session, "covered")
    request.status, request.applied_at = "Applied", _now()
    db.session.flush()  # the database accepts an applied substitute as the class trainer
    slot = _slot(session.starts_at, session.ends_at)
    if request.cover_role == "Substitute":
        change = SessionChange(session_id=session.session_id, change_type="Trainer changed", reason=f"Cover: {request.reason}",
                               old_starts_at=session.starts_at, old_ends_at=session.ends_at, old_trainer_user_id=session.trainer_user_id,
                               new_trainer_user_id=request.cover_user_id,
                               notice_hours=round((session.starts_at - _now()).total_seconds() / 3600, 1),
                               short_notice=session.starts_at - _now() < timedelta(hours=24), changed_by=actor_id())
        db.session.add(change)
        session.trainer_user_id = request.cover_user_id
    else:
        db.session.add(SessionPerson(session_id=session.session_id, role="Assistant", user_id=request.cover_user_id, added_by=actor_id()))
    db.session.flush()
    audit.record("SESSION_COVER_APPLIED", "class_session", session.session_id, branch_id=session.batch.branch_id,
                 new={"cover_role": request.cover_role, "cover_user_id": request.cover_user_id, "approved_by": request.approved_by,
                      "verified_by": request.verified_by})
    if request.cover_role == "Substitute":
        _notify_students(session, title=f"Trainer change: {session.title}", body=f"{slot}. {request.cover.full_name} will teach this class.",
                         event_key=f"cover-request-{request.request_id}-applied")
    delivery_notices.notify_users([request.cover_user_id, request.planned_trainer_user_id], category="Session",
                                  title=f"{request.cover_role} cover: {session.title}", body=f"{slot}. Scope: {request.scope}. Handover: {request.handover}",
                                  event_key=f"cover-request-{request.request_id}-applied", link=f"/sessions/{session.session_id}",
                                  branch_id=session.batch.branch_id)
    return request


def list_cover(filters: dict, page: int, per_page: int):
    stmt = (select(SessionCoverRequest).join(ClassSession, ClassSession.session_id == SessionCoverRequest.session_id)
            .join(Batch, Batch.batch_id == ClassSession.batch_id).order_by(SessionCoverRequest.requested_at.desc()))
    branch_ids = scope.visible_branch_ids()
    if branch_ids is not None:
        mine = SessionCoverRequest.cover_user_id == actor_id()
        stmt = stmt.where(Batch.branch_id.in_(branch_ids or {0}) | mine)
    if filters.get("status"):
        stmt = stmt.where(SessionCoverRequest.status == filters["status"])
    return paginate(stmt, page, per_page)


# ---------------------------------------------------------------- shared classes (Module 15 §4, §7)

def _seat_limit(session: ClassSession) -> int:
    batch = session.batch
    if session.mode == "Classroom":
        return batch.classroom_capacity if batch.classroom_capacity is not None else batch.capacity
    if session.mode == "Live Online":
        return batch.online_capacity if batch.online_capacity is not None else batch.capacity
    if batch.classroom_capacity is not None and batch.online_capacity is not None:
        return batch.classroom_capacity + batch.online_capacity
    return batch.capacity


def add_roster(session_id: int, data: dict) -> SessionRoster:
    """The Branch Manager verifies that the class covers a second batch's approved learning and joins it: one class,
    one attendance entry per person, hours and trainer time counted once."""
    session = _load_for_change(session_id)
    _require_open(session, "shared")
    if not current_user().has_role(*ACADEMIC_ROLES, branch_id=session.batch.branch_id):
        raise Forbidden("The Branch Manager, a Super Admin or the Founder verifies the coverage of a shared class")
    batch = batches_repo.get_batch(data["batch_id"])
    if batch is None:
        raise NotFound("Batch not found")
    scope.assert_can_view_batch(batch)
    delivery_access.assert_can_manage_branch(batch.branch_id)
    if batch.batch_id == session.batch_id or batch.batch_id in sessions_repo.session_batch_ids(session_id):
        raise Conflict("That batch already attends this class")
    if batch.state in ("Completed", "Cancelled", "Archived", "On Hold"):
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state}")
    if data.get("topic_id"):
        topic = catalog_repo.get_topic(data["topic_id"])
        if topic is None or topic.module.course_id != batch.course_id or topic.module.component_id != batch.component_id:
            raise ValidationError("Invalid topic", {"topic_id": [f"Not a topic of {batch.batch_code}'s course outline"]})
    people = attendance_repo.allocated_enrolments([*sessions_repo.session_batch_ids(session_id), batch.batch_id])
    distinct = len({e.student_id for e in people})
    limit = _seat_limit(session)
    if distinct > limit:
        raise BusinessRule(f"{distinct} people would attend but only {limit} seats are verified for this class")
    roster = SessionRoster(session_id=session_id, batch_id=batch.batch_id, topic_id=data.get("topic_id"), coverage_note=data["coverage_note"],
                           verified_by=actor_id())
    db.session.add(roster)
    db.session.flush()
    audit.record("SESSION_SHARED", "class_session", session_id, branch_id=session.batch.branch_id,
                 new={"batch_id": batch.batch_id, "topic_id": roster.topic_id, "coverage_note": roster.coverage_note})
    delivery_notices.notify_batch_students(batch.batch_id, title=f"New class: {session.title}", body=f"{_slot(session.starts_at, session.ends_at)} "
                                           f"(shared with {session.batch.batch_code})", event_key=f"session-shared-{session_id}-{batch.batch_id}",
                                           link=f"/sessions/{session_id}", branch_id=batch.branch_id)
    return roster


def remove_roster(session_id: int, batch_id: int) -> None:
    session = _load_for_change(session_id)
    _require_open(session, "changed")
    roster = db.session.get(SessionRoster, (session_id, batch_id))
    if roster is None:
        raise NotFound("That batch does not attend this class")
    if db.session.execute(select(AttendanceRecord.attendance_id).where(AttendanceRecord.session_id == session_id).limit(1)).first():
        raise BusinessRule("Attendance is already marked for this class")
    db.session.delete(roster)
    db.session.flush()
    audit.record("SESSION_UNSHARED", "class_session", session_id, branch_id=session.batch.branch_id, old={"batch_id": batch_id})


# ---------------------------------------------------------------- the Meet operations view (Module 16 §10)

TRACKED_JOBS = ("session-delay-check", "class-log-check", "attendance-unconfirmed", "recording-check")


def operations_view(filters: dict) -> dict:
    """One day of classes for the user's branches / batches: link and host readiness, delays and disruptions, replacement
    work, attendance awaiting the trainer, recording states, and when the background checks last succeeded."""
    if delivery_access.is_student_only():
        raise Forbidden("You don't have access to this action")
    day = filters.get("date") or today_ist()
    start = datetime.combine(day, time.min, tzinfo=IST)
    stmt = sessions_repo.list_stmt({k: filters[k] for k in ("branch_id", "batch_id", "trainer_user_id") if filters.get(k)},
                                   scope.visible_branch_ids(), scope.trainer_batch_ids(), set())
    sessions = list(db.session.execute(stmt.where(ClassSession.starts_at >= start, ClassSession.starts_at < start + timedelta(days=1))).scalars())
    ids = [s.session_id for s in sessions]
    people: dict[int, dict[str, str]] = {}
    for p in db.session.execute(select(SessionPerson).where(SessionPerson.session_id.in_(ids or [0]), SessionPerson.removed_at.is_(None),
                                                            SessionPerson.role.in_(("Host", "Backup")))).scalars():
        people.setdefault(p.session_id, {})[p.role] = p.person.full_name
    open_disruptions = {d.session_id: d for d in db.session.execute(select(SessionDisruption).where(
        SessionDisruption.session_id.in_(ids or [0]), SessionDisruption.status == "Open")).scalars()}
    recordings: dict[int, list[str]] = {}
    for session_id, status in db.session.execute(select(Recording.session_id, Recording.status).where(Recording.session_id.in_(ids or [0]))):
        recordings.setdefault(session_id, []).append(status)
    marked = dict(db.session.execute(select(AttendanceRecord.session_id, func.count()).where(AttendanceRecord.session_id.in_(ids or [0]))
                                     .group_by(AttendanceRecord.session_id)).all())

    rows = []
    for s in sessions:
        online = s.mode != "Classroom"
        seats = len(attendance_repo.allocated_enrolments(sessions_repo.session_batch_ids(s.session_id)))
        promised = s.batch.recording_provision in ("Included", "Limited") and online
        disruption = open_disruptions.get(s.session_id)
        rows.append({
            **s.to_summary(), "batch": s.batch.to_summary(), "branch": s.batch.branch.to_summary(), "mode": s.mode,
            "trainer": {"user_id": s.trainer_user_id, "full_name": s.trainer.full_name}, "purpose": s.purpose,
            "meet_status_label": meet.status_label(s.meet_status) if online else None,
            "link_ready": (s.meet_status == "Linked") if online else None,
            "host": people.get(s.session_id, {}).get("Host", s.trainer.full_name if online else None),
            "backup": people.get(s.session_id, {}).get("Backup"),
            "host_ready": (s.meet_status == "Linked" and "Backup" in people.get(s.session_id, {})) if online else None,
            "delay_notice_at": s.delay_notice_at,
            "disruption": disruption.to_dict() if disruption else None,
            "attendance": {"seats": seats, "marked": marked.get(s.session_id, 0),
                           "awaiting_confirmation": s.state in ("Live", "Delivered") and marked.get(s.session_id, 0) < seats},
            "recording": recordings.get(s.session_id) or (["Expected"] if promised and s.state != "Cancelled" else []),
            "log_overdue": s.log_overdue_at is not None,
        })

    branch_ids = scope.visible_branch_ids()
    def scoped(stmt):  # noqa: E306
        return stmt if branch_ids is None else stmt.where(Batch.branch_id.in_(branch_ids or {0}) | Batch.batch_id.in_(scope.trainer_batch_ids() or {0}))
    disruptions = db.session.execute(scoped(select(SessionDisruption).join(ClassSession, ClassSession.session_id == SessionDisruption.session_id)
                                            .join(Batch, Batch.batch_id == ClassSession.batch_id).where(SessionDisruption.status == "Open")
                                            .order_by(SessionDisruption.detected_at.desc()).limit(50))).scalars().all()
    owed = db.session.execute(scoped(select(ClassSession).join(Batch, Batch.batch_id == ClassSession.batch_id).where(
        ClassSession.state == "Cancelled", ClassSession.replacement_waiver.is_(None), ClassSession.purpose.in_(sessions_repo.OWES_REPLACEMENT),
        ClassSession.approval_status != "Rejected",
        ~ClassSession.session_id.in_(select(ClassSession.replaces_session_id).where(
            ClassSession.replaces_session_id.isnot(None), ClassSession.state != "Cancelled"))).order_by(ClassSession.starts_at).limit(50))).scalars().all()
    pending_approval = db.session.execute(scoped(select(ClassSession).join(Batch, Batch.batch_id == ClassSession.batch_id).where(
        ClassSession.approval_status == "Pending", ClassSession.state.in_(OPEN)).order_by(ClassSession.starts_at).limit(50))).scalars().all()
    missing_logs = db.session.execute(scoped(select(ClassSession).join(Batch, Batch.batch_id == ClassSession.batch_id).where(
        ClassSession.log_overdue_at.isnot(None), ClassSession.state.in_(("Scheduled", "Rescheduled", "Live")))
        .order_by(ClassSession.starts_at).limit(50))).scalars().all()
    open_recordings = db.session.execute(scoped(select(func.count()).select_from(RecordingException).join(
        ClassSession, ClassSession.session_id == RecordingException.session_id).join(Batch, Batch.batch_id == ClassSession.batch_id)
        .where(RecordingException.status != "Resolved"))).scalar_one()
    unmatched = db.session.execute(scoped(select(func.count()).select_from(MeetParticipation).join(
        ClassSession, ClassSession.session_id == MeetParticipation.session_id).join(Batch, Batch.batch_id == ClassSession.batch_id)
        .where(MeetParticipation.match_status == "Unmatched"))).scalar_one()
    runs = {r.job_name: r.to_dict() for r in db.session.execute(select(JobRun).where(JobRun.job_name.in_(TRACKED_JOBS))).scalars()}
    return {
        "date": day,
        "sessions": rows,
        "summary": {
            "classes": len(rows),
            "online_not_ready": sum(1 for r in rows if r["host_ready"] is False and r["state"] in OPEN),
            "delayed_or_disrupted": sum(1 for r in rows if r["disruption"] or r["delay_notice_at"]),
            "attendance_awaiting": sum(1 for r in rows if r["attendance"]["awaiting_confirmation"]),
        },
        "open_disruptions": [d.to_dict() for d in disruptions],
        "replacements_owed": [{**s.to_summary(), "batch": s.batch.to_summary()} for s in owed],
        "awaiting_approval": [{**s.to_summary(), "batch": s.batch.to_summary(), "purpose": s.purpose} for s in pending_approval],
        "missing_logs": [{**s.to_summary(), "batch": s.batch.to_summary(), "trainer": s.trainer.full_name} for s in missing_logs],
        "open_recording_issues": open_recordings,
        "unmatched_participants": unmatched,
        "integration": {"note": meet.integration_note(), "verified": meet.is_verified()},
        "last_runs": [runs.get(name) or {"job_name": name, "last_ok_at": None, "last_started_at": None} for name in TRACKED_JOBS],
    }
