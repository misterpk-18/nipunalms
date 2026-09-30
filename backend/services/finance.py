"""Fees & receipts: the CRM's finance summary per admission, read-only.

The CRM is authoritative for admissions and money; the LMS shows the last summary it received (with the time and source)
and never writes to it. A student sees their own admissions. A Branch Manager sees admissions serviced or collected at
their branch; Super Admin and Founder / CEO see all.
"""
from models import Admission, FinanceSummary
from repositories import finance as finance_repo
from repositories.common import paginate
from services.context import current_user
from services.errors import NotFound


def my_summaries() -> list[tuple[Admission, FinanceSummary | None]]:
    user = current_user()
    if user.student_id is None:
        raise NotFound("Student not found")
    return finance_repo.summaries_of_student(user.student_id)


def _branch_scope() -> set[int] | None:
    """Branches whose finance the user may read: None = all. Only Branch Managers (and admins) qualify."""
    user = current_user()
    if user.is_admin:
        return None
    return {s.branch_id for s in user.scopes if s.role_code == "BRANCH_MANAGER"}


def list_summaries(filters: dict, page: int, per_page: int) -> tuple[list[tuple[Admission, FinanceSummary]], dict]:
    summaries, meta = paginate(finance_repo.branch_summaries_stmt(filters, _branch_scope()), page, per_page)
    admissions = finance_repo.admissions_by_id([s.admission_id for s in summaries])
    return [(admissions[s.admission_id], s) for s in summaries], meta


def get_summary(admission_id: int) -> tuple[Admission, FinanceSummary | None]:
    found = finance_repo.summary_of_admission(admission_id)
    if found is None:
        raise NotFound("Admission not found")
    admission, summary = found
    branch_ids = _branch_scope()
    if branch_ids is not None and not {admission.service_branch_id, admission.collecting_branch_id} & branch_ids:
        raise NotFound("Admission not found")
    return admission, summary
