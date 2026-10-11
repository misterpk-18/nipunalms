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


def with_founder(limit: int | None = None) -> list[AccessExtensionRequest]:
    """Pending requests beyond the Branch Manager's limit that carry a recommendation, oldest recommendation first."""
    stmt = (select(AccessExtensionRequest).where(AccessExtensionRequest.status == "Pending", AccessExtensionRequest.needs_exception,
                                                 AccessExtensionRequest.recommended_at.is_not(None))
            .order_by(AccessExtensionRequest.recommended_at, AccessExtensionRequest.request_id))
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.session.execute(stmt).scalars().unique())


def counts(branch_ids: set[int] | None) -> dict[str, int]:
    """Pending requests at the branches: those the Branch Manager decides, and those waiting for their recommendation or the Founder."""
    from sqlalchemy import func
    stmt = select(AccessExtensionRequest.needs_exception, AccessExtensionRequest.recommended_at.is_not(None), func.count()).where(
        AccessExtensionRequest.status == "Pending").group_by(AccessExtensionRequest.needs_exception, AccessExtensionRequest.recommended_at.is_not(None))
    if branch_ids is not None:
        stmt = stmt.where(AccessExtensionRequest.branch_id.in_(branch_ids))
    out = {"decide": 0, "recommend": 0, "with_founder": 0}
    for exception, recommended, n in db.session.execute(stmt).all():
        out["decide" if not exception else ("with_founder" if recommended else "recommend")] += n
    return out
