from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated
from models.attendance import student_summary
from models.attendance_enums import ATTENDANCE_STATUSES, CORRECTION_STATUSES, RECOVERY_METHODS, RECOVERY_STATUSES
from services import attendance as attendance_service


def _register_json(register: attendance_service.Register) -> dict:
    return {
        "session": register.session.to_dict(),
        "locked": register.locked,
        "lock_days": attendance_service.lock_days(),
        "can_mark": register.can_mark,
        "summary": register.summary(),
        "rows": [
            {
                "enrolment": row.enrolment.to_summary(),
                "student": student_summary(row.enrolment),
                "attendance": row.record.to_dict() if row.record else None,
                "label": attendance_service.attendance_label(row.record, row.recovery),
                "recovery": row.recovery.to_summary() if row.recovery else None,
                "correction_pending": row.correction_pending,
            }
            for row in register.rows
        ],
    }


def list_register_sessions():
    v = Validator(request.args.to_dict())
    v.integer("batch_id", min_value=1)
    v.date("from")
    v.date("to")
    v.choice("attendance", ("pending", "marked", "locked"))
    filters = v.validate()
    page, per_page = get_page_params()
    items, meta = attendance_service.list_register_sessions(filters, page, per_page)
    return paginated([{**item["session"].to_dict(), "seats": item["seats"], "marked": item["marked"],
                       "attendance_state": item["attendance_state"], "locked": item["locked"], "can_mark": item["can_mark"]}
                      for item in items], meta)


def get_register(session_id: int):
    return ok(_register_json(attendance_service.get_register(session_id)))


def mark_attendance(session_id: int):
    v = Validator(json_body())
    v.choice("default_status", ATTENDANCE_STATUSES, nullable=True)

    def entry_rules(entry: Validator) -> None:
        entry.integer("enrolment_id", required=True, min_value=1)
        entry.choice("status", ATTENDANCE_STATUSES, required=True)
        entry.string("remarks", nullable=True, max_length=500)

    v.list_of("entries", entry_rules)
    data = v.validate()
    return ok(_register_json(attendance_service.mark_attendance(session_id, data.get("entries", []), data.get("default_status"))))


def my_attendance():
    return ok(attendance_service.my_attendance())


def enrolment_attendance(enrolment_id: int):
    return ok(attendance_service.get_enrolment_attendance(enrolment_id))


# ---------------------------------------------------------------- recoveries

def list_recoveries():
    v = Validator(request.args.to_dict())
    v.choice("status", RECOVERY_STATUSES)
    v.integer("batch_id", min_value=1)
    v.integer("enrolment_id", min_value=1)
    filters = v.validate()
    page, per_page = get_page_params()
    rows, meta = attendance_service.list_recoveries(filters, page, per_page)
    return paginated([r.to_dict() for r in rows], meta)


def request_recovery():
    v = Validator(json_body())
    v.integer("attendance_id", required=True, min_value=1)
    v.choice("method", RECOVERY_METHODS, required=True)
    v.string("reason", required=True, max_length=1000)
    data = v.validate()
    return created(attendance_service.request_recovery(data["attendance_id"], data["method"], data["reason"]).to_dict())


def decide_recovery(recovery_id: int):
    v = Validator(json_body())
    v.choice("decision", ("Approved", "Rejected"), required=True)
    v.string("decision_note", nullable=True, max_length=1000)
    v.date("target_date", nullable=True)
    data = v.validate()
    recovery = attendance_service.decide_recovery(recovery_id, data["decision"], data.get("decision_note"), data.get("target_date"))
    return ok(recovery.to_dict())


def complete_recovery(recovery_id: int):
    v = Validator(json_body())
    v.string("evidence_note", required=True, max_length=1000)
    return ok(attendance_service.complete_recovery(recovery_id, v.validate()["evidence_note"]).to_dict())


# ---------------------------------------------------------------- corrections

def list_corrections():
    v = Validator(request.args.to_dict())
    v.choice("status", CORRECTION_STATUSES)
    v.integer("batch_id", min_value=1)
    filters = v.validate()
    page, per_page = get_page_params()
    rows, meta = attendance_service.list_corrections(filters, page, per_page)
    return paginated([c.to_dict() for c in rows], meta)


def request_correction():
    v = Validator(json_body())
    v.integer("session_id", required=True, min_value=1)
    v.integer("enrolment_id", required=True, min_value=1)
    v.choice("requested_status", ATTENDANCE_STATUSES, required=True)
    v.string("reason", required=True, max_length=1000)
    data = v.validate()
    correction = attendance_service.request_correction(data["session_id"], data["enrolment_id"], data["requested_status"], data["reason"])
    return created(correction.to_dict())


def decide_correction(correction_id: int):
    v = Validator(json_body())
    v.choice("decision", ("Approved", "Rejected"), required=True)
    v.string("decision_note", nullable=True, max_length=1000)
    data = v.validate()
    return ok(attendance_service.decide_correction(correction_id, data["decision"], data.get("decision_note")).to_dict())
