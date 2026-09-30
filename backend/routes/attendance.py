"""Attendance, recovery and correction endpoints (plus the student's own /me/attendance)."""
from flask import Blueprint

from controllers import attendance as attendance_controller
from routes.decorators import fresh_auth, login_required, require_roles

attendance_bp = Blueprint("attendance", __name__)

STAFF = ("TRAINER", "ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
EVERYONE = ("STUDENT",) + STAFF
MARKERS = ("TRAINER", "ACADEMIC_COORDINATOR", "SUPER_ADMIN")


@attendance_bp.get("/attendance/sessions")
@login_required
@require_roles(*STAFF)
def list_register_sessions():
    return attendance_controller.list_register_sessions()


@attendance_bp.get("/attendance/sessions/<int:session_id>")
@login_required
@require_roles(*STAFF)
def get_register(session_id: int):
    return attendance_controller.get_register(session_id)


@attendance_bp.put("/attendance/sessions/<int:session_id>")
@login_required
@require_roles(*MARKERS)
def mark_attendance(session_id: int):
    return attendance_controller.mark_attendance(session_id)


@attendance_bp.get("/me/attendance")
@login_required
@require_roles("STUDENT")
def my_attendance():
    return attendance_controller.my_attendance()


@attendance_bp.get("/attendance/enrolments/<int:enrolment_id>")
@login_required
@require_roles(*EVERYONE)
def enrolment_attendance(enrolment_id: int):
    return attendance_controller.enrolment_attendance(enrolment_id)


@attendance_bp.get("/attendance/recoveries")
@login_required
@require_roles(*EVERYONE)
def list_recoveries():
    return attendance_controller.list_recoveries()


@attendance_bp.post("/attendance/recoveries")
@login_required
@require_roles("STUDENT", *MARKERS)
def request_recovery():
    return attendance_controller.request_recovery()


@attendance_bp.post("/attendance/recoveries/<int:recovery_id>/decision")
@login_required
@require_roles("ACADEMIC_COORDINATOR", "SUPER_ADMIN")
def decide_recovery(recovery_id: int):
    return attendance_controller.decide_recovery(recovery_id)


@attendance_bp.post("/attendance/recoveries/<int:recovery_id>/completion")
@login_required
@require_roles(*MARKERS)
def complete_recovery(recovery_id: int):
    return attendance_controller.complete_recovery(recovery_id)


@attendance_bp.get("/attendance/corrections")
@login_required
@require_roles(*EVERYONE)
def list_corrections():
    return attendance_controller.list_corrections()


@attendance_bp.post("/attendance/corrections")
@login_required
@require_roles("STUDENT", *MARKERS)
def request_correction():
    return attendance_controller.request_correction()


@attendance_bp.post("/attendance/corrections/<int:correction_id>/decision")
@login_required
@require_roles("ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN")
@fresh_auth
def decide_correction(correction_id: int):
    return attendance_controller.decide_correction(correction_id)
