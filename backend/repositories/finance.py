"""Admissions with their read-only finance summary."""
from sqlalchemy import Select, or_, select

from config.database import db
from models import Admission, FinanceSummary, Student


def summaries_of_student(student_id: int) -> list[tuple[Admission, FinanceSummary | None]]:
    """Every admission of the student, with the CRM's summary when one has arrived."""
    stmt = (
        select(Admission, FinanceSummary)
        .outerjoin(FinanceSummary, FinanceSummary.admission_id == Admission.admission_id)
        .where(Admission.student_id == student_id)
        .order_by(Admission.admission_id)
    )
    return [(row[0], row[1]) for row in db.session.execute(stmt).all()]


def branch_summaries_stmt(filters: dict, branch_ids: set[int] | None) -> Select:
    """Finance summaries of admissions serviced or collected at the visible branches (None = all)."""
    stmt = (
        select(FinanceSummary)
        .join(Admission, FinanceSummary.admission_id == Admission.admission_id)
        .join(Student, Student.student_id == Admission.student_id)
        .order_by(Student.full_name, Admission.admission_id)
    )
    if branch_ids is not None:
        stmt = stmt.where(or_(Admission.service_branch_id.in_(branch_ids), Admission.collecting_branch_id.in_(branch_ids)))
    if filters.get("branch_id"):
        stmt = stmt.where(or_(Admission.service_branch_id == filters["branch_id"], Admission.collecting_branch_id == filters["branch_id"]))
    if filters.get("student_id"):
        stmt = stmt.where(Admission.student_id == filters["student_id"])
    if filters.get("has_balance"):
        stmt = stmt.where(FinanceSummary.balance > 0)
    return stmt


def summary_of_admission(admission_id: int) -> tuple[Admission, FinanceSummary | None] | None:
    stmt = (
        select(Admission, FinanceSummary)
        .outerjoin(FinanceSummary, FinanceSummary.admission_id == Admission.admission_id)
        .where(Admission.admission_id == admission_id)
    )
    row = db.session.execute(stmt).first()
    return (row[0], row[1]) if row else None


def admissions_by_id(admission_ids: list[int]) -> dict[int, Admission]:
    rows = db.session.execute(select(Admission).where(Admission.admission_id.in_(admission_ids))).scalars()
    return {a.admission_id: a for a in rows}


def all_of(stmt: Select) -> list[FinanceSummary]:
    """Every summary a branch_summaries_stmt matches (for totals across pages)."""
    return list(db.session.execute(stmt.order_by(None)).scalars())


def summaries_on_invoice(invoice_number: str) -> list[tuple[Admission, FinanceSummary]]:
    """The admissions whose summary is on this CRM invoice (one invoice can cover several courses)."""
    stmt = (
        select(Admission, FinanceSummary)
        .join(FinanceSummary, FinanceSummary.admission_id == Admission.admission_id)
        .where(FinanceSummary.invoice_numbers.contains([invoice_number]))
        .order_by(Admission.admission_id)
    )
    return [(row[0], row[1]) for row in db.session.execute(stmt).all()]
