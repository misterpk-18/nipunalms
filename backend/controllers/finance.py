from flask import request

from controllers.common import Validator, get_page_params, ok, paginated
from services import finance as finance_service

SOURCE = "CRM (authoritative) — read-only"
PENDING_NOTE = "A payment that is still Pending Verification is not a receipt and is not counted as paid."


def _entry(admission, summary) -> dict:
    return {
        "admission": admission.to_summary(),
        "student": {"student_id": admission.student_id},
        "course": admission.course.to_summary(),
        "service_branch": admission.service_branch.to_summary(),
        "collecting_branch": admission.collecting_branch.to_summary(),
        "summary": summary.to_dict() if summary else None,
        "source": SOURCE,
    }


def my_finance():
    return ok({"source": SOURCE, "note": PENDING_NOTE, "admissions": [_entry(a, s) for a, s in finance_service.my_summaries()]})


def list_summaries():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    v.integer("student_id", min_value=1)
    v.boolean("has_balance")
    page, per_page = get_page_params()
    rows, meta = finance_service.list_summaries(v.validate(), page, per_page)
    return paginated([_entry(a, s) for a, s in rows], meta)


def get_summary(admission_id: int):
    return ok(_entry(*finance_service.get_summary(admission_id)))
