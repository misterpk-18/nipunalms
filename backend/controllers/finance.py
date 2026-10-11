from flask import Response, request

from controllers.common import Validator, get_page_params, json_body, ok, paginated, require_changes
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
        "schedule_key": finance_service.schedule_key(summary) if summary else None,
        "source": SOURCE,
    }


def _schedule(schedule: finance_service.Schedule) -> dict:
    """One instalment schedule, shown once: an invoice's lists every course (admission) it covers."""
    source = schedule.source
    return {
        "schedule_key": schedule.key,
        "invoice_number": schedule.invoice_number,
        "installments_scope": schedule.scope,
        "invoice_course_count": schedule.course_count,
        "admissions": [{**a.to_summary(), "course": a.course.to_summary()} for a in schedule.admissions],
        "installments": source.installments,
        "next_due_date": source.next_due_date,
        "next_due_amount": source.next_due_amount,
        "overdue_amount": finance_service.overdue_amount(source),
        "as_of": source.as_of,
    }


def my_finance():
    rows = finance_service.my_summaries()
    return ok({"source": SOURCE, "note": PENDING_NOTE, "admissions": [_entry(a, s) for a, s in rows],
               "schedules": [_schedule(s) for s in finance_service.schedules_of(rows)],
               "next_payment": finance_service.next_payment(rows)})


def my_receipt_pdf(admission_id: int, receipt_number: str):
    content, filename = finance_service.receipt_pdf(admission_id, receipt_number)
    return Response(content, mimetype="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"',
                                                                  "Cache-Control": "private, no-store"})


def get_payment_instructions(branch_id: int):
    branch = finance_service.get_payment_instructions(branch_id)
    return ok({**branch.to_summary(), "payment_instructions": branch.payment_instructions})


def set_payment_instructions(branch_id: int):
    v = Validator(json_body())
    v.string("payment_instructions", nullable=True, max_length=1500)
    branch = finance_service.set_payment_instructions(branch_id, require_changes(v.validate())["payment_instructions"])
    return ok({**branch.to_summary(), "payment_instructions": branch.payment_instructions})


def list_summaries():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    v.integer("student_id", min_value=1)
    v.boolean("has_balance")
    page, per_page = get_page_params()
    rows, meta = finance_service.list_summaries(v.validate(), page, per_page)
    return paginated([_entry(a, s) for a, s in rows], meta)


def get_summary(admission_id: int):
    admission, summary, schedule = finance_service.get_summary(admission_id)
    return ok({**_entry(admission, summary), "schedule": _schedule(schedule) if schedule else None})
