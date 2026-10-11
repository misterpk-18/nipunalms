"""`GET /me/requests`: what the signed-in staff member asked for and what became of it (UX plan U12, recovery requests added in
U13): reschedule requests, attendance corrections and recovery requests, newest first, each with its status, who decided and why.

Status words are one set for all three kinds (Pending, Approved, Rejected). While a request waits, `decides` names who will decide:
the Branch Manager, or the Founder / Super Admin when the person asking is a Branch Manager (services/approvals.py).
"""
from models import AttendanceCorrection, AttendanceRecovery, SessionChangeRequest
from models.attendance import student_summary
from repositories import attendance as attendance_repo
from repositories import class_sessions as sessions_repo
from repositories import users as users_repo
from services.class_sessions import _slot
from services.context import current_user

PAGE = 100


def _session(session) -> dict:
    return {"session_id": session.session_id, "title": session.title, "starts_at": session.starts_at, "ends_at": session.ends_at,
            "batch": session.batch.to_summary()}


def _decided_by(user) -> dict | None:
    return {"user_id": user.user_id, "full_name": user.full_name} if user else None


def _reschedule(request: SessionChangeRequest, decides: str) -> dict:
    session = request.session
    proposed = _slot(request.proposed_starts_at, request.proposed_ends_at)
    return {
        "kind": "reschedule",
        "id": request.request_id,
        "status": "Pending" if request.status == "Open" else request.status,
        "title": f"Move {session.title}",
        "summary": (f"Moved to {proposed}" if request.status == "Approved" else f"From {_slot(session.starts_at, session.ends_at)} to {proposed}"),
        "reason": request.reason,
        "requested_at": request.created_at,
        "decided_by": _decided_by(request.decider),
        "decided_at": request.decided_at,
        "decision_note": request.decision_note,
        "decides": decides,
        "session": _session(session),
    }


def _correction(correction: AttendanceCorrection, decides: str) -> dict:
    student = student_summary(correction.enrolment)
    return {
        "kind": "correction",
        "id": correction.correction_id,
        "status": correction.status,
        "title": f"Attendance of {student['full_name']}",
        "summary": f"{correction.previous_status or 'Not marked'} to {correction.requested_status} in {correction.session.title}",
        "reason": correction.reason,
        "requested_at": correction.requested_at,
        "decided_by": _decided_by(correction.decider),
        "decided_at": correction.decided_at,
        "decision_note": correction.decision_note,
        "decides": decides,
        "session": _session(correction.session),
    }


def _recovery(recovery: AttendanceRecovery, decides: str) -> dict:
    record = recovery.attendance
    student = student_summary(record.enrolment)
    done = recovery.status == "Completed"
    return {
        "kind": "recovery",
        "id": recovery.recovery_id,
        # One set of words: asked (Pending), then approved (the plan stands, or it was carried out) or not approved
        "status": {"Requested": "Pending", "Approved": "Approved", "Completed": "Approved", "Rejected": "Rejected"}[recovery.status],
        "title": f"Recovery for {student['full_name']}",
        "summary": f"{recovery.method} for the class {record.session.title}" + (" (done)" if done else ""),
        "reason": recovery.reason,
        "requested_at": recovery.requested_at,
        "decided_by": _decided_by(users_repo.get_by_id(recovery.decided_by)) if recovery.decided_by else None,
        "decided_at": recovery.decided_at,
        "decision_note": recovery.decision_note,
        "decides": decides,
        "session": _session(record.session),
    }


def list_mine() -> dict:
    user = current_user()
    # A Branch Manager's own requests go to the Founder / Super Admin; everyone else's to the Branch Manager
    decides = "Founder or Super Admin" if user.has_role("BRANCH_MANAGER") else "Branch Manager"
    rows = ([_reschedule(r, decides) for r in sessions_repo.requests_by_user(user.user_id, PAGE)]
            + [_correction(c, decides) for c in attendance_repo.corrections_by_user(user.user_id, PAGE)]
            + [_recovery(r, decides) for r in attendance_repo.recoveries_by_user(user.user_id, PAGE)])
    rows.sort(key=lambda row: row["requested_at"], reverse=True)
    waiting = sum(1 for row in rows if row["status"] == "Pending")
    return {"items": rows[:PAGE], "counts": {"waiting": waiting, "decided": len(rows) - waiting}}
