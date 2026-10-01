"""Enrolment lists for staff (people lists, the allocation queue) and locked loads for seat changes."""
from datetime import date

from sqlalchemy import Select, select

from config.database import db
from models import Admission, BatchAllocation, Enrolment, Student


def get_enrolment_for_update(enrolment_id: int) -> Enrolment | None:
    """The enrolment, row-locked so two seat changes on it are serialised."""
    return db.session.execute(
        select(Enrolment).where(Enrolment.enrolment_id == enrolment_id).with_for_update(of=Enrolment).execution_options(populate_existing=True)
    ).scalar_one_or_none()


def students_by_id(student_ids: set[int]) -> dict[int, Student]:
    if not student_ids:
        return {}
    return {s.student_id: s for s in db.session.execute(select(Student).where(Student.student_id.in_(student_ids))).scalars()}


def list_stmt(filters: dict, branch_ids: set[int] | None, tied_enrolment_ids: set[int]) -> Select:
    """Enrolments in the user's branches (None = all) or tied to them (a trainer's students), narrowed by the filters."""
    stmt = select(Enrolment).join(Student, Student.student_id == Enrolment.student_id).order_by(Enrolment.service_branch_id, Student.full_name,
                                                                                                Enrolment.enrolment_id)
    if branch_ids is not None:
        stmt = stmt.where(Enrolment.service_branch_id.in_(branch_ids) | Enrolment.enrolment_id.in_(tied_enrolment_ids))
    if filters.get("branch_id"):
        stmt = stmt.where(Enrolment.service_branch_id == filters["branch_id"])
    if filters.get("course_id"):
        stmt = stmt.where(Enrolment.course_id == filters["course_id"])
    if filters.get("status"):
        stmt = stmt.where(Enrolment.status == filters["status"])
    if filters.get("kind"):
        stmt = stmt.where(Enrolment.kind == filters["kind"])
    if filters.get("batch_id"):
        stmt = stmt.where(Enrolment.enrolment_id.in_(
            select(BatchAllocation.enrolment_id).where(BatchAllocation.batch_id == filters["batch_id"], BatchAllocation.status == "Active")))
    if filters.get("q"):
        pattern = f"%{filters['q']}%"
        stmt = stmt.where(Student.full_name.ilike(pattern) | Student.student_code.ilike(pattern) | Enrolment.enrolment_code.ilike(pattern))
    return stmt


def unallocated_starting_by(last_start: date, statuses: tuple[str, ...]) -> list[Enrolment]:
    """Enrolments still waiting for a seat whose admission is planned to start on or before `last_start`."""
    stmt = (
        select(Enrolment)
        .join(Admission, Admission.admission_id == Enrolment.admission_id)
        .where(Enrolment.status.in_(statuses), Admission.crm_status != "Cancelled",
               Admission.planned_start_date.is_not(None), Admission.planned_start_date <= last_start)
        .order_by(Admission.planned_start_date, Enrolment.enrolment_id)
    )
    return list(db.session.execute(stmt).scalars())
