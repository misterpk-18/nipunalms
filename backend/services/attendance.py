"""Attendance per actual Class Session x allocated enrolment, recovery for absences, and corrections.

The assigned trainer (or a Branch Manager) marks Present / Absent / Late / Excused for a Live or Delivered session.
No entry means "Not yet marked", never a guessed absence. Entries lock `attendance_lock_days` after the session ends;
after that (or for a student's dispute) a correction needs an independent reviewer's approval. The first Present / Late
entry of an enrolment sets its joining date and moves it from "Allocated — awaiting first regular class" to Active.
A recovery (REC-0041) for an absence is raised by the student or trainer, approved by the Branch Manager and
verified on completion; the original Absent entry is never rewritten.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from config.database import db
from config.timezone import IST, today_ist
from models import AttendanceCorrection, AttendanceRecord, AttendanceRecovery, ClassSession, Enrolment
from repositories import attendance as attendance_repo
from repositories import batches as batches_repo
from repositories import class_sessions as sessions_repo
from repositories import settings as settings_repo
from repositories import students as students_repo
from repositories import users as users_repo
from repositories.common import paginate
from repositories.rows import paginate_rows
from services import approvals, audit, certificates, progress, scope, working_days
from services.context import current_user
from services.errors import BusinessRule, Conflict, Forbidden, NotFound, ValidationError
from services.notifications import notify

ATTENDED = ("Present", "Late")
MARKERS = ("BRANCH_MANAGER",)       # besides the batch's trainers
DECIDERS = ("BRANCH_MANAGER",)  # correction reviewers (independent of the requester); the Founder / Super Admin decide a Branch Manager's own
RECOVERY_APPROVERS = ("BRANCH_MANAGER",)


def lock_days() -> int:
    return settings_repo.get_int("attendance_lock_days", 7)


def is_locked(session: ClassSession, now: datetime | None = None) -> bool:
    """Locked once `attendance_lock_days` have passed since the session ended."""
    return (now or datetime.now(timezone.utc)) > session.ends_at + timedelta(days=lock_days())


def attendance_label(record: AttendanceRecord | None, recovery: AttendanceRecovery | None) -> str:
    """The wording students and staff see: 'Absent — recovery approved (REC-0041)', 'Present (trainer-confirmed)' ..."""
    if record is None:
        return "Not yet marked"
    if record.status == "Absent":
        if recovery is None:
            return "Absent"
        return f"Absent — recovery {recovery.status.lower()} ({recovery.recovery_code})"
    return f"{record.status} (trainer-confirmed)"


def class_date(session: ClassSession) -> date:
    return session.starts_at.astimezone(IST).date()


def _student_user_ids(student_id: int) -> list[int]:
    user = users_repo.get_by_student_id(student_id)
    return [user.user_id] if user else []


def _snapshot(record: AttendanceRecord) -> dict:
    return {"status": record.status, "remarks": record.remarks}


# ---------------------------------------------------------------- joining date

def set_joining_date(enrolment: Enrolment, on: date) -> bool:
    """The first regular Present / Late entry: sets the joining date and starts the enrolment (Active). True when it changed.

    Called from marking and from an approved correction; the batch and session APIs (S1) never set it.
    """
    if enrolment.joining_date is not None and enrolment.joining_date <= on:
        return False
    old = {"joining_date": enrolment.joining_date, "status": enrolment.status}
    enrolment.joining_date = on
    if enrolment.status == "Allocated — awaiting first regular class":
        enrolment.status = "Active"
    db.session.flush()
    audit.record("ENROLMENT_JOINED", "enrolment", enrolment.enrolment_code, old=old,
                 new={"joining_date": enrolment.joining_date, "status": enrolment.status}, branch_id=enrolment.service_branch_id)
    if enrolment.status == "Active":
        certificates.ensure_register_entry(enrolment)
    return True


# ---------------------------------------------------------------- the register of one session

@dataclass
class RegisterRow:
    enrolment: Enrolment
    record: AttendanceRecord | None
    recovery: AttendanceRecovery | None
    correction_pending: bool


@dataclass
class Register:
    session: ClassSession
    rows: list[RegisterRow]
    locked: bool
    can_mark: bool

    def summary(self) -> dict:
        counts = {status: 0 for status in ("Present", "Absent", "Late", "Excused")}
        for row in self.rows:
            if row.record is not None:
                counts[row.record.status] += 1
        marked = sum(counts.values())
        return {"seats": len(self.rows), "marked": marked, "not_yet_marked": len(self.rows) - marked,
                **{status.lower(): n for status, n in counts.items()}}


def _teaches(session: ClassSession) -> bool:
    """The class's trainer (an approved substitute too) or a trainer of its batch."""
    user = current_user()
    return user.has_role("TRAINER") and (session.trainer_user_id == user.user_id or session.batch_id in scope.trainer_batch_ids())


def _can_mark(session: ClassSession) -> bool:
    return _teaches(session) or current_user().has_role(*MARKERS, branch_id=session.batch.branch_id)


def _visible_session(session_id: int) -> ClassSession:
    session = attendance_repo.get_session(session_id)
    if session is None:
        raise NotFound("Class session not found")
    if not _teaches(session):
        scope.assert_can_view_batch(session.batch)
    return session


def get_register(session_id: int) -> Register:
    session = _visible_session(session_id)
    records = attendance_repo.records_for_session(session_id)
    enrolments = attendance_repo.allocated_enrolments(sessions_repo.session_batch_ids(session.session_id))
    seated = {e.enrolment_id for e in enrolments}
    # Someone who moved to another batch after being marked keeps their entry on this session's register
    enrolments += [r.enrolment for r in records.values() if r.enrolment_id not in seated]

    recoveries = attendance_repo.recoveries_by_attendance([r.attendance_id for r in records.values()])
    pending = attendance_repo.pending_correction_keys([session_id])
    rows = []
    for enrolment in enrolments:
        record = records.get(enrolment.enrolment_id)
        rows.append(RegisterRow(enrolment, record, recoveries.get(record.attendance_id) if record else None,
                                (session_id, enrolment.enrolment_id) in pending))
    return Register(session, rows, is_locked(session), _can_mark(session))


def list_register_sessions(filters: dict, page: int, per_page: int) -> tuple[list[dict], dict]:
    """Live / Delivered sessions with how many seats are marked: the trainer's pending list and the Branch Manager's oversight."""
    if filters.get("batch_id"):
        batch = batches_repo.get_batch(filters["batch_id"])
        if batch is None:
            raise NotFound("Batch not found")
        scope.assert_can_view_batch(batch)
    now = datetime.now(timezone.utc)
    stmt = attendance_repo.register_sessions_stmt(filters, scope.visible_branch_ids(), scope.trainer_batch_ids(), now, lock_days())
    rows, meta = paginate_rows(stmt, page, per_page)
    items = []
    for session, allocated, marked in rows:
        locked = is_locked(session, now)
        state = ("Not yet marked" if marked == 0 else "Marked" if marked >= allocated else "Partially marked") if allocated else "No seats"
        items.append({"session": session, "seats": allocated, "marked": marked, "attendance_state": state, "locked": locked,
                      "can_mark": _can_mark(session)})
    return items, meta


# ---------------------------------------------------------------- marking

def mark_attendance(session_id: int, entries: list[dict], default_status: str | None) -> Register:
    """Mark the register: `entries` per enrolment, and/or default_status for every seat with no entry yet.

    "Mark everyone Present, then fix the exceptions" is one call: default_status="Present" plus the exceptions as entries.
    """
    session = _visible_session(session_id)
    if not _can_mark(session):
        raise Forbidden("Only the batch's trainers or the Branch Manager can mark attendance")
    if session.state not in ("Live", "Delivered"):
        raise BusinessRule(f"Attendance can only be marked for a Live or Delivered session (this one is {session.state})")
    if is_locked(session):
        raise BusinessRule(f"Attendance for {session.session_code} is locked ({lock_days()} days after the session). "
                           "Request a correction; an independent reviewer approves it")

    seats = {e.enrolment_id: e for e in attendance_repo.allocated_enrolments(sessions_repo.session_batch_ids(session.session_id))}
    entered = {entry["enrolment_id"] for entry in entries}
    if len(entered) != len(entries):
        raise ValidationError("Invalid request data", {"entries": ["An enrolment appears twice"]})
    unknown = entered - set(seats)
    if unknown:
        raise BusinessRule(f"Enrolment(s) {sorted(unknown)} do not hold a seat in {session.batch.batch_code}")

    existing = attendance_repo.records_for_session(session_id)
    plan = list(entries) + [{"enrolment_id": eid, "status": default_status, "remarks": None}
                            for eid in seats if default_status and eid not in entered and eid not in existing]
    if not plan:
        raise ValidationError("Invalid request data", {"entries": ["Nothing to mark"]})

    user = current_user()
    now = datetime.now(timezone.utc)
    changes, newly_absent = {}, []
    for item in plan:
        enrolment = seats[item["enrolment_id"]]
        status, remarks = item["status"], item.get("remarks") or None
        record = existing.get(enrolment.enrolment_id)
        if record is None:
            record = AttendanceRecord(session_id=session_id, enrolment_id=enrolment.enrolment_id, status=status, remarks=remarks,
                                      marked_by=user.user_id, marked_at=now)
            db.session.add(record)
            changes[enrolment.enrolment_code] = {"old": None, "new": status}
        elif (record.status, record.remarks) != (status, remarks):
            changes[enrolment.enrolment_code] = {"old": record.status, "new": status}
            record.status, record.remarks, record.marked_by, record.marked_at = status, remarks, user.user_id, now
        else:
            continue
        db.session.flush()
        if status in ATTENDED:
            set_joining_date(enrolment, class_date(session))
        if status == "Absent" and changes[enrolment.enrolment_code]["old"] != "Absent":
            newly_absent.append(enrolment)

    if changes:
        audit.record("ATTENDANCE_MARKED", "class_session", session.session_code, new={"entries": changes},
                     branch_id=session.batch.branch_id)
    for enrolment in newly_absent:
        notify(category="Attendance", title=f"Marked absent: {session.title}",
               body="Your trainer marked you absent. You can request recovery from My Progress.",
               link="/progress?tab=attendance", branch_id=session.batch.branch_id, recipient_user_ids=_student_user_ids(enrolment.student_id),
               event_key=f"attendance-absent:{session.session_id}:{enrolment.enrolment_id}")
    return get_register(session_id)


# ---------------------------------------------------------------- one enrolment's attendance

def _recovery_status(recovery: AttendanceRecovery | None) -> dict | None:
    """A recovery request as the student sees it: its status, the decision note and who decides (the Branch Manager)."""
    if recovery is None:
        return None
    return {**recovery.to_summary(), "decision_note": recovery.decision_note, "target_date": recovery.target_date,
            "decided_at": recovery.decided_at, "decides": "Branch Manager"}


def _correction_status(correction: AttendanceCorrection | None) -> dict | None:
    """The latest "report a mistake" request for a class: what was asked, its status, the decision note and who decides."""
    if correction is None:
        return None
    return {"correction_id": correction.correction_id, "status": correction.status, "requested_status": correction.requested_status,
            "reason": correction.reason, "requested_at": correction.requested_at, "decided_at": correction.decided_at,
            "decision_note": correction.decision_note, "decides": "Branch Manager"}


def enrolment_attendance(enrolment: Enrolment) -> dict:
    """Attendance measure plus one row per Live / Delivered session since the seat (what the student's Attendance screen shows)."""
    session_rows = attendance_repo.student_session_rows(enrolment.enrolment_id)
    records = [r for _, r in session_rows if r is not None]
    recoveries = attendance_repo.recoveries_by_attendance([r.attendance_id for r in records])
    pending = attendance_repo.pending_correction_keys([s.session_id for s, _ in session_rows])
    corrections = attendance_repo.latest_corrections([s.session_id for s, _ in session_rows], enrolment.enrolment_id)
    now = datetime.now(timezone.utc)
    rows = []
    for session, record in session_rows:
        recovery = recoveries.get(record.attendance_id) if record else None
        rows.append({
            "session": {"session_id": session.session_id, "session_code": session.session_code, "title": session.title,
                        "starts_at": session.starts_at, "ends_at": session.ends_at, "mode": session.mode, "state": session.state,
                        "trainer": {"user_id": session.trainer_user_id, "full_name": session.trainer.full_name},
                        "batch": session.batch.to_summary()},
            "attendance_id": record.attendance_id if record else None,
            "status": record.status if record else None,
            "label": attendance_label(record, recovery),
            "remarks": record.remarks if record else None,
            "marked_at": record.marked_at if record else None,
            "locked": is_locked(session, now),
            "recovery": _recovery_status(recovery),
            "correction": _correction_status(corrections.get(session.session_id)),
            "correction_pending": (session.session_id, enrolment.enrolment_id) in pending,
            "can_request_recovery": record is not None and record.status == "Absent" and recovery is None,
        })
    return {"enrolment": enrolment.to_summary(), "joining_date": enrolment.joining_date,
            "summary": progress.get_enrolment_progress(enrolment.enrolment_id)["attendance"], "rows": rows}


def my_attendance() -> list[dict]:
    """Every enrolment of the signed-in student that is (or was) being taught, each with its attendance rows."""
    student_id = current_user().student_id
    if student_id is None:
        raise NotFound("This login has no student record")
    enrolments = [e for e in students_repo.enrolments_of_student(student_id)
                  if e.status in ("Allocated — awaiting first regular class", "Active", "Paused", "Completed")]
    return [enrolment_attendance(e) for e in enrolments]


def get_enrolment_attendance(enrolment_id: int) -> dict:
    return enrolment_attendance(progress.get_visible_enrolment(enrolment_id))


# ---------------------------------------------------------------- recovery

def _get_recovery(recovery_id: int) -> AttendanceRecovery:
    recovery = attendance_repo.get_recovery(recovery_id)
    if recovery is None:
        raise NotFound("Recovery not found")
    scope.assert_can_view_enrolment(recovery.attendance.enrolment)
    return recovery


def list_recoveries(filters: dict, page: int, per_page: int) -> tuple[list[AttendanceRecovery], dict]:
    return paginate(attendance_repo.recoveries_stmt(filters, progress.visible_enrolment_condition()), page, per_page)


def request_recovery(attendance_id: int, method: str, reason: str) -> AttendanceRecovery:
    """The student (for their own absence) or the trainer of the batch asks to recover a missed session."""
    record = attendance_repo.get_record(attendance_id)
    if record is None:
        raise NotFound("Attendance entry not found")
    scope.assert_can_view_enrolment(record.enrolment)
    if record.status != "Absent":
        raise BusinessRule("Recovery can only be requested for an Absent entry")
    live = attendance_repo.live_recovery(attendance_id)
    if live is not None:
        raise Conflict(f"{live.recovery_code} already exists for this absence ({live.status})")
    recovery = AttendanceRecovery(attendance_id=attendance_id, method=method, reason=reason, requested_by=current_user().user_id)
    db.session.add(recovery)
    db.session.flush()
    db.session.refresh(recovery)
    enrolment = record.enrolment
    audit.record("RECOVERY_REQUESTED", "attendance_recovery", recovery.recovery_code,
                 new={"method": method, "session": record.session.session_code, "enrolment": enrolment.enrolment_code},
                 reason=reason, branch_id=enrolment.service_branch_id)
    notify(category="Attendance", title=f"Recovery requested ({recovery.recovery_code})",
           body=f"{students_repo.get_student(enrolment.student_id).full_name} — {record.session.title}: {method}",
           link="/branch/attendance", role_code="BRANCH_MANAGER", branch_id=enrolment.service_branch_id,
           event_key=f"recovery-requested:{recovery.recovery_id}", action_required=True)
    return recovery


def decide_recovery(recovery_id: int, decision: str, note: str | None, target_date: date | None) -> AttendanceRecovery:
    recovery = _get_recovery(recovery_id)
    enrolment = recovery.attendance.enrolment
    if not current_user().has_role(*RECOVERY_APPROVERS, branch_id=enrolment.service_branch_id):
        raise Forbidden("Only the Branch Manager can decide a recovery")
    if recovery.status != "Requested":
        raise BusinessRule(f"{recovery.recovery_code} is already {recovery.status}")
    if decision == "Rejected" and not note:
        raise ValidationError("Invalid request data", {"decision_note": ["Give the reason for rejecting the recovery"]})
    recovery.status = decision
    recovery.decided_by = current_user().user_id
    recovery.decided_at = datetime.now(timezone.utc)
    recovery.decision_note = note
    recovery.target_date = target_date
    db.session.flush()
    audit.record("RECOVERY_DECIDED", "attendance_recovery", recovery.recovery_code, old={"status": "Requested"},
                 new={"status": decision, "target_date": target_date}, reason=note, branch_id=enrolment.service_branch_id)
    notify(category="Attendance", title=f"Recovery {decision.lower()} ({recovery.recovery_code})",
           body=note or f"Your recovery for {recovery.attendance.session.title} was approved. Complete it as agreed.",
           link="/progress?tab=attendance", branch_id=enrolment.service_branch_id, recipient_user_ids=_student_user_ids(enrolment.student_id),
           event_key=f"recovery-decided:{recovery.recovery_id}")
    if recovery.requested_by not in _student_user_ids(enrolment.student_id):
        # Raised by a trainer for the student: the trainer hears the decision too, on My requests
        notify(category="Attendance", title=f"Recovery {decision.lower()} ({recovery.recovery_code})",
               body=note or f"The recovery you asked for ({recovery.attendance.session.title}) was approved.",
               link="/trainer/requests", branch_id=enrolment.service_branch_id, recipient_user_ids=[recovery.requested_by],
               event_key=f"recovery-decided-requester:{recovery.recovery_id}")
    return recovery


def complete_recovery(recovery_id: int, evidence_note: str) -> AttendanceRecovery:
    """Verify that the approved recovery was done (a recording link alone is not evidence)."""
    recovery = _get_recovery(recovery_id)
    enrolment = recovery.attendance.enrolment
    user = current_user()
    batch_id = recovery.attendance.session.batch_id
    is_trainer = user.has_role("TRAINER") and batch_id in scope.trainer_batch_ids()
    if not (is_trainer or user.has_role(*RECOVERY_APPROVERS, branch_id=enrolment.service_branch_id)):
        raise Forbidden("Only the batch's trainer or the Branch Manager can verify a recovery")
    if recovery.status != "Approved":
        raise BusinessRule(f"{recovery.recovery_code} is {recovery.status}; only an approved recovery can be completed")
    recovery.status = "Completed"
    recovery.completed_by = user.user_id
    recovery.completed_at = datetime.now(timezone.utc)
    recovery.evidence_note = evidence_note
    db.session.flush()
    audit.record("RECOVERY_COMPLETED", "attendance_recovery", recovery.recovery_code, old={"status": "Approved"},
                 new={"status": "Completed"}, reason=evidence_note, branch_id=enrolment.service_branch_id)
    notify(category="Attendance", title=f"Recovery completed ({recovery.recovery_code})", body="Your trainer verified your recovery work.",
           link="/progress?tab=attendance", branch_id=enrolment.service_branch_id, recipient_user_ids=_student_user_ids(enrolment.student_id),
           event_key=f"recovery-completed:{recovery.recovery_id}")
    return recovery


# ---------------------------------------------------------------- corrections

def _get_correction(correction_id: int) -> AttendanceCorrection:
    correction = attendance_repo.get_correction(correction_id)
    if correction is None:
        raise NotFound("Correction request not found")
    scope.assert_can_view_enrolment(correction.enrolment)
    return correction


def list_corrections(filters: dict, page: int, per_page: int) -> tuple[list[AttendanceCorrection], dict]:
    return paginate(attendance_repo.corrections_stmt(filters, progress.visible_enrolment_condition()), page, per_page)


def can_decide_correction(correction: AttendanceCorrection) -> bool:
    """Whether the current user may decide it (the screen hides the buttons otherwise): a Branch Manager of the branch who is not the
    requester or the person who marked the entry, and an admin when the requester is a Branch Manager."""
    if correction.status != "Pending" or not (current_user().has_role(*DECIDERS, branch_id=correction.enrolment.service_branch_id)
                                              or approvals.admin_may_decide(correction.requested_by)):
        return False
    record = attendance_repo.find_record(correction.session_id, correction.enrolment_id)
    if record is not None and record.marked_by == current_user().user_id:
        return False
    return approvals.can_decide(correction.requested_by)


def request_correction(session_id: int, enrolment_id: int, requested_status: str, reason: str) -> AttendanceCorrection:
    """A student's dispute, or a trainer's or Branch Manager's change to an entry that is locked (or was never marked)."""
    enrolment = progress.get_visible_enrolment(enrolment_id)
    session = attendance_repo.get_session(session_id)
    if session is None or not attendance_repo.has_seat_history(enrolment_id, sessions_repo.session_batch_ids(session.session_id)):
        raise NotFound("Class session not found for this enrolment")
    if session.state not in ("Live", "Delivered"):
        raise BusinessRule("Only a Live or Delivered session has attendance to correct")
    record = attendance_repo.find_record(session_id, enrolment_id)
    previous = record.status if record else None
    if previous == requested_status:
        raise BusinessRule(f"The entry already says {requested_status}")
    if attendance_repo.pending_correction(session_id, enrolment_id) is not None:
        raise Conflict("A correction for this session is already awaiting a decision")
    correction = AttendanceCorrection(session_id=session_id, enrolment_id=enrolment_id, requested_status=requested_status,
                                      previous_status=previous, reason=reason, requested_by=current_user().user_id)
    db.session.add(correction)
    db.session.flush()
    audit.record("ATTENDANCE_CORRECTION_REQUESTED", "attendance_correction", correction.correction_id,
                 old={"status": previous}, new={"status": requested_status}, reason=reason, branch_id=enrolment.service_branch_id)
    notify(category="Attendance", title=f"Attendance correction requested: {session.title}",
           body=f"{students_repo.get_student(enrolment.student_id).full_name}: {previous or 'Not yet marked'} to {requested_status}. {reason}",
           link="/branch/attendance", role_code="BRANCH_MANAGER", branch_id=enrolment.service_branch_id,
           event_key=f"correction-requested:{correction.correction_id}", action_required=True)
    return correction


def decide_correction(correction_id: int, decision: str, note: str | None) -> AttendanceCorrection:
    """Approve (the entry changes, audited) or reject. The decider must not be the requester or the person who marked the entry."""
    correction = _get_correction(correction_id)
    enrolment = correction.enrolment
    user = current_user()
    if not (user.has_role(*DECIDERS, branch_id=enrolment.service_branch_id) or approvals.admin_may_decide(correction.requested_by)):
        raise Forbidden("Only the Branch Manager can decide an attendance correction")
    if correction.status != "Pending":
        raise BusinessRule(f"This correction is already {correction.status}")
    record = attendance_repo.find_record(correction.session_id, correction.enrolment_id)
    approvals.require_independent(correction.requested_by, record.marked_by if record is not None else None,
                                  message="An independent reviewer must decide: not the requester and not the person who marked the entry",
                                  requester=correction.requested_by)
    if decision == "Rejected" and not note:
        raise ValidationError("Invalid request data", {"decision_note": ["Give the reason for rejecting the correction"]})

    correction.status = decision
    correction.decided_by = user.user_id
    correction.decided_at = datetime.now(timezone.utc)
    correction.decision_note = note
    if decision == "Approved":
        _apply_correction(correction, record)
    db.session.flush()
    audit.record("ATTENDANCE_CORRECTION_DECIDED", "attendance_correction", correction.correction_id,
                 old={"status": correction.previous_status}, new={"decision": decision, "status": correction.requested_status},
                 reason=note, branch_id=enrolment.service_branch_id)
    if correction.requested_by != user.user_id:
        notify(category="Attendance", title=f"Attendance correction {decision.lower()}: {correction.session.title}",
               body=note or (f"The entry now says {correction.requested_status}." if decision == "Approved" else "The entry stays as it was."),
               link="/progress?tab=attendance" if correction.requester.student_id else "/trainer/requests",  # a student's request or a trainer's
               branch_id=enrolment.service_branch_id, recipient_user_ids=[correction.requested_by],
               event_key=f"correction-decided:{correction.correction_id}")
    return correction


def _apply_correction(correction: AttendanceCorrection, record: AttendanceRecord | None) -> None:
    """Change (or create) the entry; the reviewer and time are kept on it and the old value stays in the audit log."""
    user = current_user()
    now = datetime.now(timezone.utc)
    reason = correction.reason
    if record is None:
        record = AttendanceRecord(session_id=correction.session_id, enrolment_id=correction.enrolment_id,
                                  status=correction.requested_status, remarks=reason, marked_by=user.user_id, marked_at=now,
                                  corrected_by=user.user_id, corrected_at=now)
        db.session.add(record)
    else:
        record.status, record.remarks = correction.requested_status, reason
        record.corrected_by, record.corrected_at = user.user_id, now
    db.session.flush()
    if record.status in ATTENDED:
        set_joining_date(correction.enrolment, class_date(correction.session))


# ---------------------------------------------------------------- confirmation (Module 21 §3)

def alert_unconfirmed() -> int:
    """Job `attendance-unconfirmed`: the trainer confirms attendance by the end of the class's working day; from the next
    academic working day, a delivered class with seats still unmarked alerts the branch's Branch Manager (once per
    class). The class date and the later confirmation (`marked_at`) stay separate. Returns how many classes were raised."""
    today = today_ist()
    lookback = settings_repo.get_int("attendance_unconfirmed_lookback_days", 14)
    raised = 0
    for session, missing in attendance_repo.sessions_missing_attendance(today - timedelta(days=lookback), today - timedelta(days=1)):
        class_day = class_date(session)
        if today < working_days.add_working_days(class_day, 1, session.batch.branch_id):
            continue  # the trainer still has until the end of the class's working day
        sent = notify(category="Attendance", title=f"Attendance not confirmed: {session.session_code} ({class_day:%d %b})",
                      body=f"{session.title} · {session.batch.batch_code} · {missing} student(s) not yet marked by "
                           f"{session.trainer.full_name}.",
                      link="/branch/attendance", role_code="BRANCH_MANAGER", branch_id=session.batch.branch_id,
                      event_key=f"attendance-unconfirmed:{session.session_id}", action_required=True)
        raised += 1 if sent else 0
    return raised

