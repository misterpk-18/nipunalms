"""Access extension requests."""
from sqlalchemy import Select, select

from config.database import db
from models import AccessExtensionRequest


def get(request_id: int) -> AccessExtensionRequest | None:
    return db.session.get(AccessExtensionRequest, request_id)


def approved_for_enrolment(enrolment_id: int) -> list[AccessExtensionRequest]:
    return approved_for_enrolments([enrolment_id]).get(enrolment_id, [])


def approved_for_enrolments(enrolment_ids: list[int]) -> dict[int, list[AccessExtensionRequest]]:
    if not enrolment_ids:
        return {}
    stmt = select(AccessExtensionRequest).where(
        AccessExtensionRequest.enrolment_id.in_(enrolment_ids), AccessExtensionRequest.status == "Approved"
    )
    grouped: dict[int, list[AccessExtensionRequest]] = {}
    for request in db.session.execute(stmt).scalars():
        grouped.setdefault(request.enrolment_id, []).append(request)
    return grouped


def pending_for_enrolment(enrolment_id: int) -> list[AccessExtensionRequest]:
    stmt = select(AccessExtensionRequest).where(
        AccessExtensionRequest.enrolment_id == enrolment_id, AccessExtensionRequest.status == "Pending"
    )
    return list(db.session.execute(stmt).scalars())


def list_stmt(filters: dict, branch_ids: set[int] | None, student_id: int | None) -> Select:
    """Requests of one student, or of the branches (None = all), newest first, narrowed by the filters."""
    stmt = select(AccessExtensionRequest).order_by(AccessExtensionRequest.requested_at.desc(), AccessExtensionRequest.request_id.desc())
    if student_id is not None:
        stmt = stmt.where(AccessExtensionRequest.student_id == student_id)
    elif branch_ids is not None:
        stmt = stmt.where(AccessExtensionRequest.branch_id.in_(branch_ids))
    for column in ("status", "scope", "enrolment_id", "branch_id", "student_id"):
        if filters.get(column) is not None and not (column == "student_id" and student_id is not None):
            stmt = stmt.where(getattr(AccessExtensionRequest, column) == filters[column])
    if filters.get("needs_exception") is not None:
        stmt = stmt.where(AccessExtensionRequest.needs_exception == filters["needs_exception"])
    return stmt
