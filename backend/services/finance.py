"""Fees & receipts: the CRM's finance summary per admission, read-only.

The CRM is authoritative for admissions and money; the LMS shows the last summary it received (with the time and source)
and never writes to it. A student sees their own admissions. A Branch Manager sees admissions serviced or collected at
their branch; Super Admin and Founder / CEO see all.

Instalments are kept by the CRM per invoice. When one invoice covers several courses (one admission each), every one of
those admissions' summaries carries the same invoice schedule (installments_scope = 'invoice'). The per-course figures
(fee, verified, balance, receipts…) stay per admission and can be summed; the schedule and its next due are shown and
summed once per invoice, never once per admission.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from config.timezone import IST, today_ist
from models import Admission, Branch, FinanceSummary
from repositories import branches as branches_repo
from repositories import finance as finance_repo
from repositories import students as students_repo
from repositories.common import paginate
from services import audit, pdf, scope
from services.context import current_user
from services.errors import NotFound

ZERO = Decimal("0.00")


@dataclass
class Schedule:
    """One instalment schedule: an invoice's (shared by its admissions), or one admission's own."""

    key: str
    invoice_number: str | None
    scope: str
    course_count: int
    source: FinanceSummary  # the most recent summary that carries the schedule
    admissions: list[Admission] = field(default_factory=list)


def schedule_key(summary: FinanceSummary) -> str:
    if summary.installments_scope == "invoice" and summary.invoice_numbers:
        return f"invoice:{summary.invoice_numbers[0]}"
    return f"admission:{summary.admission_id}"


def schedules_of(rows: list[tuple[Admission, FinanceSummary | None]]) -> list[Schedule]:
    """The distinct schedules behind these admissions, in the order they first appear."""
    schedules: dict[str, Schedule] = {}
    for admission, summary in rows:
        if summary is None:
            continue
        key = schedule_key(summary)
        schedule = schedules.get(key)
        if schedule is None:
            schedule = schedules[key] = Schedule(
                key=key, invoice_number=summary.invoice_numbers[0] if summary.invoice_numbers else None,
                scope=summary.installments_scope, course_count=summary.invoice_course_count, source=summary)
        elif (summary.as_of, summary.source_version) > (schedule.source.as_of, schedule.source.source_version):
            schedule.source, schedule.course_count = summary, summary.invoice_course_count
        schedule.admissions.append(admission)
    return list(schedules.values())


def overdue_amount(summary: FinanceSummary, today: date | None = None) -> Decimal:
    """What is overdue on this summary's schedule: the CRM's due_position, else a past due date with a balance."""
    today = today or today_ist()
    total = ZERO
    for item in summary.installments:
        position = item.get("due_position")
        overdue = position == "Overdue" if position else date.fromisoformat(item["due_date"]) < today
        if overdue:
            total += Decimal(item.get("balance") or "0")
    return total


def totals(summaries: list[FinanceSummary]) -> dict:
    """Per-course balances are summed per admission; overdue and next due are summed once per schedule."""
    by_schedule = {schedule_key(s): s for s in sorted(summaries, key=lambda s: (s.as_of, s.source_version))}
    return {
        "admissions": len(summaries),
        "balance": sum((s.balance for s in summaries), ZERO),
        "schedules": len(by_schedule),
        "overdue_amount": sum((overdue_amount(s) for s in by_schedule.values()), ZERO),
        "next_due_amount": sum((s.next_due_amount or ZERO for s in by_schedule.values()), ZERO),
    }


def my_summaries() -> list[tuple[Admission, FinanceSummary | None]]:
    user = current_user()
    if user.student_id is None:
        raise NotFound("Student not found")
    return finance_repo.summaries_of_student(user.student_id)


def _branch_scope() -> set[int] | None:
    """Branches whose finance the user may read: None = all. Only Branch Managers (and admins) qualify."""
    return scope.visible_branch_ids()


def list_summaries(filters: dict, page: int, per_page: int) -> tuple[list[tuple[Admission, FinanceSummary]], dict]:
    stmt = finance_repo.branch_summaries_stmt(filters, _branch_scope())
    summaries, meta = paginate(stmt, page, per_page)
    admissions = finance_repo.admissions_by_id([s.admission_id for s in summaries])
    meta["totals"] = totals(finance_repo.all_of(stmt))
    return [(admissions[s.admission_id], s) for s in summaries], meta


def get_summary(admission_id: int) -> tuple[Admission, FinanceSummary | None, Schedule | None]:
    """One admission, with the schedule it is on (an invoice's schedule lists every admission of that invoice)."""
    found = finance_repo.summary_of_admission(admission_id)
    if found is None:
        raise NotFound("Admission not found")
    admission, summary = found
    branch_ids = _branch_scope()
    if branch_ids is not None and not {admission.service_branch_id, admission.collecting_branch_id} & branch_ids:
        raise NotFound("Admission not found")
    if summary is None:
        return admission, None, None
    rows = [(admission, summary)]
    if summary.installments_scope == "invoice" and summary.invoice_numbers:
        rows = finance_repo.summaries_on_invoice(summary.invoice_numbers[0])
    [schedule] = [s for s in schedules_of(rows) if s.key == schedule_key(summary)]
    return admission, summary, schedule


# ---------------------------------------------------------------- what the student sees first

def next_payment(rows: list[tuple[Admission, FinanceSummary | None]], today: date | None = None) -> dict:
    """The "Next payment" card: the nearest instalment still to pay across the student's schedules, whether anything is overdue,
    and how to pay at the branch that collects it. `state` is `unknown` (the CRM has sent nothing), `paid` (no balance left) or
    `due`. Amounts and dates are the CRM's; the LMS only picks the earliest and flags a date that has passed."""
    today = today or today_ist()
    summaries = [s for _, s in rows if s is not None]
    if not summaries:
        return {"state": "unknown"}
    schedules = schedules_of(rows)
    candidates = [s for s in schedules if s.source.next_due_date and (s.source.next_due_amount or ZERO) > 0]
    overdue = sum((overdue_amount(s.source, today) for s in schedules), ZERO)
    if not candidates and overdue <= 0:
        return {"state": "paid" if all(s.balance <= 0 for s in summaries) else "unknown"}
    chosen = min(candidates, key=lambda s: s.source.next_due_date) if candidates else schedules[0]
    branch = chosen.admissions[0].collecting_branch
    due_date = chosen.source.next_due_date
    return {
        "state": "due",
        "due_date": due_date,
        "amount": chosen.source.next_due_amount,
        "overdue_amount": overdue,
        "is_overdue": overdue > 0 or (due_date is not None and due_date < today),
        "courses": [a.course.title for a in chosen.admissions],
        "invoice_number": chosen.invoice_number,
        "how_to_pay": {"branch": branch.to_summary(), "instructions": branch.payment_instructions},
    }


def receipt_pdf(admission_id: int, receipt_number: str) -> tuple[bytes, str]:
    """A receipt the CRM has verified, drawn from its finance record. Only the student the admission belongs to may download it."""
    user = current_user()
    found = finance_repo.summary_of_admission(admission_id)
    if user.student_id is None or found is None or found[0].student_id != user.student_id or found[1] is None:
        raise NotFound("Receipt not found")
    admission, summary = found
    receipt = next((r for r in summary.receipts if r["receipt_number"] == receipt_number), None)
    if receipt is None:
        raise NotFound("Receipt not found")
    student = students_repo.get_student(user.student_id)
    content = pdf.render_receipt({
        "branch_name": admission.collecting_branch.branch_name, "receipt_number": receipt["receipt_number"],
        "receipt_date": date.fromisoformat(receipt["date"]), "amount": Decimal(receipt["amount"]),
        "student_name": student.full_name, "student_code": student.student_code, "admission_code": admission.admission_code,
        "course_title": admission.course.title, "invoice_numbers": summary.invoice_numbers, "fee_total": summary.fee_total,
        "verified_paid": summary.verified_paid, "balance": summary.balance, "as_of": summary.as_of.astimezone(IST).date(),
    })
    audit.record("RECEIPT_DOWNLOADED", "admission", admission.admission_code, new={"receipt_number": receipt_number},
                 branch_id=admission.service_branch_id)
    return content, f"receipt-{receipt_number}.pdf"


# ---------------------------------------------------------------- branch setting

def get_payment_instructions(branch_id: int) -> Branch:
    """The branch whose payment instructions are being read or set: 404 outside the user's branches."""
    branch = branches_repo.get_by_id(branch_id)
    visible = scope.visible_branch_ids(current_user())
    if branch is None or (visible is not None and branch_id not in visible):
        raise NotFound("Branch not found")
    return branch


def set_payment_instructions(branch_id: int, instructions: str | None) -> Branch:
    """How and where students pay at this branch. A Branch Manager sets it for their own branches; a Super Admin for any."""
    branch = get_payment_instructions(branch_id)
    old = branch.payment_instructions
    branch.payment_instructions = instructions or None
    audit.record("BRANCH_PAYMENT_INSTRUCTIONS_CHANGED", "branch", branch.branch_code, old={"payment_instructions": old},
                 new={"payment_instructions": branch.payment_instructions}, branch_id=branch.branch_id)
    return branch
