"""Career profiles, CV versions, opportunities, applications and placement outcomes."""
from datetime import date

from sqlalchemy import Select, or_, select, text
from sqlalchemy.orm import selectinload

from config.database import db
from models import Application, CareerProfile, CvDocument, Opportunity, PlacementOutcome, Student
from models.career import CLOSED_APPLICATION_STATUSES


# ---------------------------------------------------------------- profiles

def get_profile(student_id: int) -> CareerProfile | None:
    return db.session.get(CareerProfile, student_id)


def profiles_stmt(filters: dict, branch_ids: set[int] | None) -> Select:
    """Career profiles of students serviced at the visible branches (None = all)."""
    stmt = select(CareerProfile).join(Student, Student.student_id == CareerProfile.student_id).order_by(Student.full_name, Student.student_id)
    if branch_ids is not None:
        stmt = stmt.where(Student.service_branch_id.in_(branch_ids))
    if filters.get("branch_id"):
        stmt = stmt.where(Student.service_branch_id == filters["branch_id"])
    if filters.get("opted_in") is not None:
        stmt = stmt.where(CareerProfile.opted_in == filters["opted_in"])
    if filters.get("readiness"):
        stmt = stmt.where(CareerProfile.readiness == filters["readiness"])
    if filters.get("q"):
        pattern = f"%{filters['q']}%"
        stmt = stmt.where(or_(Student.full_name.ilike(pattern), Student.student_code.ilike(pattern)))
    return stmt


# ---------------------------------------------------------------- CVs

def get_cv(cv_id: int) -> CvDocument | None:
    return db.session.get(CvDocument, cv_id)


def cvs_of_student(student_id: int) -> list[CvDocument]:
    stmt = select(CvDocument).where(CvDocument.student_id == student_id).order_by(CvDocument.version_no.desc())
    return list(db.session.execute(stmt).scalars())


def latest_reviewed_cv(student_id: int) -> CvDocument | None:
    stmt = (
        select(CvDocument)
        .where(CvDocument.student_id == student_id, CvDocument.review_status == "Reviewed")
        .order_by(CvDocument.version_no.desc())
        .limit(1)
    )
    return db.session.execute(stmt).scalars().first()


def supersede_cvs(student_id: int) -> None:
    """A new upload supersedes the older versions that are still current (they stay on file)."""
    for cv in cvs_of_student(student_id):
        if cv.review_status != "Superseded":
            cv.review_status = "Superseded"


# ---------------------------------------------------------------- opportunities

def get_opportunity(opportunity_id: int) -> Opportunity | None:
    return db.session.get(Opportunity, opportunity_id)


def opportunities_stmt(filters: dict, branch_ids: set[int] | None) -> Select:
    """Staff view: every status; an opportunity tied to a branch is visible to that branch's staff."""
    stmt = select(Opportunity).order_by(Opportunity.created_at.desc(), Opportunity.opportunity_id.desc())
    if branch_ids is not None:
        stmt = stmt.where(or_(Opportunity.branch_id.is_(None), Opportunity.branch_id.in_(branch_ids)))
    if filters.get("status"):
        stmt = stmt.where(Opportunity.status == filters["status"])
    if filters.get("course_id"):
        stmt = stmt.where(Opportunity.course_id == filters["course_id"])
    if filters.get("q"):
        pattern = f"%{filters['q']}%"
        stmt = stmt.where(or_(Opportunity.title.ilike(pattern), Opportunity.employer_name.ilike(pattern)))
    return stmt


def eligible_opportunities(course_ids: set[int], branch_ids: set[int], today: date) -> list[Opportunity]:
    """Active opportunities still open, for the student's courses and branches (NULL = open to all)."""
    stmt = (
        select(Opportunity)
        .where(
            Opportunity.status == "Active",
            or_(Opportunity.closing_date.is_(None), Opportunity.closing_date >= today),
            or_(Opportunity.course_id.is_(None), Opportunity.course_id.in_(course_ids)),
            or_(Opportunity.branch_id.is_(None), Opportunity.branch_id.in_(branch_ids)),
        )
        .order_by(Opportunity.created_at.desc(), Opportunity.opportunity_id.desc())
    )
    return list(db.session.execute(stmt).scalars())


# ---------------------------------------------------------------- applications

def get_application(application_id: int) -> Application | None:
    return db.session.get(Application, application_id)


def find_application(student_id: int, opportunity_id: int, hiring_cycle: str) -> Application | None:
    return db.session.execute(
        select(Application).where(Application.student_id == student_id, Application.opportunity_id == opportunity_id,
                                  Application.hiring_cycle == hiring_cycle)
    ).scalar_one_or_none()


def applications_of_student(student_id: int) -> list[Application]:
    stmt = select(Application).where(Application.student_id == student_id).order_by(Application.applied_at.desc(), Application.application_id.desc())
    return list(db.session.execute(stmt).scalars())


def applications_stmt(filters: dict, branch_ids: set[int] | None) -> Select:
    stmt = (
        select(Application)
        .join(Student, Student.student_id == Application.student_id)
        .options(selectinload(Application.events))
        .order_by(Application.updated_at.desc(), Application.application_id.desc())
    )
    if branch_ids is not None:
        stmt = stmt.where(Student.service_branch_id.in_(branch_ids))
    if filters.get("status"):
        stmt = stmt.where(Application.status == filters["status"])
    if filters.get("open"):
        stmt = stmt.where(Application.status.not_in(CLOSED_APPLICATION_STATUSES))
    if filters.get("student_id"):
        stmt = stmt.where(Application.student_id == filters["student_id"])
    if filters.get("opportunity_id"):
        stmt = stmt.where(Application.opportunity_id == filters["opportunity_id"])
    return stmt


# ---------------------------------------------------------------- outcomes

def get_outcome(outcome_id: int) -> PlacementOutcome | None:
    return db.session.get(PlacementOutcome, outcome_id)


def outcomes_of_student(student_id: int) -> list[PlacementOutcome]:
    stmt = select(PlacementOutcome).where(PlacementOutcome.student_id == student_id).order_by(PlacementOutcome.event_date.desc())
    return list(db.session.execute(stmt).scalars())


def outcomes_stmt(filters: dict, branch_ids: set[int] | None) -> Select:
    stmt = (
        select(PlacementOutcome)
        .join(Student, Student.student_id == PlacementOutcome.student_id)
        .order_by(PlacementOutcome.event_date.desc(), PlacementOutcome.outcome_id.desc())
    )
    if branch_ids is not None:
        stmt = stmt.where(Student.service_branch_id.in_(branch_ids))
    if filters.get("student_id"):
        stmt = stmt.where(PlacementOutcome.student_id == filters["student_id"])
    if filters.get("verification_status"):
        stmt = stmt.where(PlacementOutcome.verification_status == filters["verification_status"])
    return stmt


def verified_outcome_counts(branch_ids: set[int] | None) -> list[tuple[str, int, int]]:
    """(outcome type, outcomes, distinct students) from the verified_placement_outcomes view."""
    query = "SELECT outcome_type, COUNT(*), COUNT(DISTINCT student_id) FROM verified_placement_outcomes"
    params: dict = {}
    if branch_ids is not None:
        query += " WHERE branch_id = ANY(:branches)"
        params["branches"] = list(branch_ids)
    rows = db.session.execute(text(query + " GROUP BY outcome_type ORDER BY outcome_type"), params).all()
    return [(row[0], row[1], row[2]) for row in rows]

