"""Placement & career support (Module 23): assistance only, never a placement guarantee.

Students opt in, keep a career profile and CV versions, browse approved opportunities and apply; staff (Academic
Coordinator, Branch Manager, Super Admin) run the opportunity register, review CVs and readiness, move applications
through the hiring stages and record outcomes. An outcome (offer, acceptance, joining) counts in reports only once a
second person has Verified it with evidence.
"""
import calendar
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from werkzeug.datastructures import FileStorage

from config.database import db
from config.timezone import IST, today_ist
from models import Application, CareerProfile, CvDocument, Opportunity, PlacementOutcome, Student
from models.career import CLOSED_APPLICATION_STATUSES
from repositories import career as career_repo
from repositories import students as students_repo
from repositories import users as users_repo
from repositories.common import paginate
from services import audit, cv_storage, scope
from services.context import current_user
from services.errors import BusinessRule, Conflict, NotFound, ValidationError
from services.notifications import notify

SUPPORT_MONTHS = 6  # career support after opting in (Data Pack 8A: six months after completion)
PROFILE_FIELDS = (
    ("preferred_roles", "Preferred roles"), ("preferred_locations", "Preferred locations"), ("work_mode", "Work mode"),
    ("qualification", "Qualification"), ("graduation_year", "Graduation year"), ("experience_level", "Fresher or experienced"),
    ("skills", "Skills"), ("portfolio_url", "Portfolio or project link"), ("availability", "Availability"),
)
# Where an opportunity may move (Module 23 §7); Closed and Expired are final
OPPORTUNITY_TRANSITIONS = {
    "Draft": ("Verification Pending", "Closed"),
    "Verification Pending": ("Active", "Draft", "Closed"),
    "Active": ("On Hold", "Closed"),
    "On Hold": ("Active", "Closed"),
    "Closed": (),
    "Expired": (),
}
EDITABLE_OPPORTUNITY_STATUSES = ("Draft", "Verification Pending", "On Hold")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


@dataclass
class CareerOverview:
    student: Student
    profile: CareerProfile | None
    completeness: dict
    cvs: list[CvDocument]
    opportunities: list[Opportunity]
    applied_opportunity_ids: set[int]
    applications: list[Application]
    outcomes: list[PlacementOutcome]
    next_action: str


# ---------------------------------------------------------------- profile helpers

def completeness(profile: CareerProfile | None, has_reviewed_cv: bool) -> dict:
    """Share of the profile filled in (%), and what is still missing."""
    missing = [label for field, label in PROFILE_FIELDS if not (profile and getattr(profile, field))]
    if not has_reviewed_cv:
        missing.append("A reviewed CV")
    total = len(PROFILE_FIELDS) + 1
    return {"percent": round(100 * (total - len(missing)) / total), "missing": missing}


def _student(student_id: int | None = None) -> Student:
    """The signed-in student, or the given student for staff (out of branch scope is a 404)."""
    user = current_user()
    if student_id is None:
        if user.student_id is None:
            raise NotFound("Student not found")
        return students_repo.get_student(user.student_id)
    student = students_repo.get_student(student_id)
    if student is None:
        raise NotFound("Student not found")
    scope.assert_can_view_student(student)
    return student


def _get_or_create_profile(student_id: int) -> CareerProfile:
    profile = career_repo.get_profile(student_id)
    if profile is None:
        profile = CareerProfile(student_id=student_id)
        db.session.add(profile)
        db.session.flush()
    return profile


def _next_action(profile: CareerProfile | None, has_reviewed_cv: bool, applications: list[Application]) -> str:
    now = _now()
    upcoming = [a for a in applications if a.interview_at and a.interview_at > now and a.status not in CLOSED_APPLICATION_STATUSES]
    if profile is None or not profile.opted_in:
        return "Opt in to career support to start preparing your profile and CV."
    if upcoming:
        nxt = min(upcoming, key=lambda a: a.interview_at)
        label = nxt.interview_round or "your interview"
        return f"Prepare for {label} ({nxt.interview_at.astimezone(IST).strftime('%d %b')})."
    if not has_reviewed_cv:
        return "Upload a CV so it can be reviewed before you apply."
    if not profile.sharing_consent:
        return "Give consent to share your profile with employers to apply for opportunities."
    return "Browse the approved opportunities and apply to the ones that match your goals."


# ---------------------------------------------------------------- student: overview and profile

def overview() -> CareerOverview:
    student = _student()
    profile = career_repo.get_profile(student.student_id)
    cvs = career_repo.cvs_of_student(student.student_id)
    has_reviewed = any(cv.review_status == "Reviewed" for cv in cvs)
    applications = career_repo.applications_of_student(student.student_id)
    return CareerOverview(
        student=student, profile=profile, completeness=completeness(profile, has_reviewed), cvs=cvs,
        opportunities=_eligible_for(student) if profile and profile.opted_in else [],
        applied_opportunity_ids={a.opportunity_id for a in applications},
        applications=applications, outcomes=career_repo.outcomes_of_student(student.student_id),
        next_action=_next_action(profile, has_reviewed, applications),
    )


def _eligible_for(student: Student) -> list[Opportunity]:
    enrolments = [e for e in students_repo.enrolments_of_student(student.student_id) if e.status != "Withdrawn"]
    course_ids = {e.course_id for e in enrolments}
    branch_ids = {student.service_branch_id} | {e.service_branch_id for e in enrolments}
    return career_repo.eligible_opportunities(course_ids, branch_ids, today_ist())


def update_profile(data: dict) -> CareerProfile:
    student = _student()
    profile = _get_or_create_profile(student.student_id)
    was_opted_in = profile.opted_in

    if "opted_in" in data:
        if data["opted_in"] and not was_opted_in:
            today = today_ist()
            profile.opted_in, profile.opted_in_at = True, _now()
            # A late opt-in uses the remaining period; a first opt-in gets the standard support window
            profile.support_start = profile.support_start or today
            profile.support_end = profile.support_end or _add_months(profile.support_start, SUPPORT_MONTHS)
            audit.record("CAREER_OPT_IN", "career_profile", student.student_code, new={"support_end": profile.support_end},
                         branch_id=student.service_branch_id)
        elif not data["opted_in"] and was_opted_in:
            profile.opted_in, profile.sharing_consent, profile.sharing_consent_at = False, False, None
            audit.record("CAREER_OPT_OUT", "career_profile", student.student_code, branch_id=student.service_branch_id)

    for field in ("preferred_roles", "preferred_locations", "work_mode", "qualification", "graduation_year", "experience_level",
                  "portfolio_url", "availability"):
        if field in data:
            setattr(profile, field, data[field])
    if "skills" in data:
        known = {s["name"].lower(): s for s in profile.skills}
        profile.skills = [known.get(name.lower(), {"name": name, "confidence": "Student Reported"}) for name in data["skills"]]
    db.session.flush()
    return profile


def set_consent(consent: bool) -> CareerProfile:
    """Permission to share the profile with employers; separate from opting in. Withdrawing never recalls what was already sent."""
    student = _student()
    profile = career_repo.get_profile(student.student_id)
    if profile is None or not profile.opted_in:
        raise BusinessRule("Opt in to career support first")
    if profile.sharing_consent != consent:
        profile.sharing_consent = consent
        profile.sharing_consent_at = _now() if consent else None
        audit.record("CAREER_CONSENT_GIVEN" if consent else "CAREER_CONSENT_WITHDRAWN", "career_profile", student.student_code,
                     new={"sharing_consent": consent}, branch_id=student.service_branch_id)
    return profile


def upload_cv(upload: FileStorage | None, label: str | None) -> CvDocument:
    student = _student()
    profile = career_repo.get_profile(student.student_id)
    if profile is None or not profile.opted_in:
        raise BusinessRule("Opt in to career support before uploading a CV")
    stored = cv_storage.save_cv(upload, student.student_id)
    career_repo.supersede_cvs(student.student_id)
    cv = CvDocument(student_id=student.student_id, label=label or Path(stored["original_filename"]).stem[:150], **stored)
    db.session.add(cv)
    db.session.flush()
    db.session.refresh(cv)
    audit.record("CV_UPLOADED", "cv_document", cv.cv_id, new={"version_no": cv.version_no, "student": student.student_code},
                 branch_id=student.service_branch_id)
    notify(category="Career", title=f"CV v{cv.version_no} uploaded for review", body=f"{student.full_name}: {cv.label}",
           link="/academic/support", event_key=f"cv:{cv.cv_id}:uploaded", role_code="ACADEMIC_COORDINATOR",
           branch_id=student.service_branch_id)
    return cv


def download_cv(cv_id: int) -> tuple[CvDocument, Path]:
    """The CV file for its student, or for staff who see that student; anyone else gets a 404."""
    cv = career_repo.get_cv(cv_id)
    if cv is None:
        raise NotFound("CV not found")
    _student(cv.student_id)
    return cv, cv_storage.absolute_path(cv.file_path)


# ---------------------------------------------------------------- student: applications

def apply(opportunity_id: int) -> Application:
    student = _student()
    profile = career_repo.get_profile(student.student_id)
    if profile is None or not profile.opted_in:
        raise BusinessRule("Opt in to career support before applying")
    if not profile.sharing_consent:
        raise BusinessRule("Give consent to share your profile with employers before applying")
    cv = career_repo.latest_reviewed_cv(student.student_id)
    if cv is None:
        raise BusinessRule("Upload a CV and wait for it to be reviewed before applying")
    opportunity = next((o for o in _eligible_for(student) if o.opportunity_id == opportunity_id), None)
    if opportunity is None:
        raise NotFound("Opportunity not found")
    if career_repo.find_application(student.student_id, opportunity_id, "Current") is not None:
        raise Conflict("You have already applied to this opportunity")

    application = Application(student_id=student.student_id, opportunity_id=opportunity_id, cv_id=cv.cv_id, source="Nipuna-referred")
    db.session.add(application)
    db.session.flush()
    audit.record("APPLICATION_SUBMITTED", "application", application.application_id,
                 new={"student": student.student_code, "opportunity": opportunity.opportunity_code, "cv_version": cv.version_no},
                 branch_id=student.service_branch_id)
    notify(category="Career", title=f"{student.full_name} applied for {opportunity.title}", body=opportunity.employer_name,
           link="/academic/support", event_key=f"application:{application.application_id}:applied",
           role_code="ACADEMIC_COORDINATOR", branch_id=student.service_branch_id)
    return application


def withdraw(application_id: int) -> Application:
    student = _student()
    application = career_repo.get_application(application_id)
    if application is None or application.student_id != student.student_id:
        raise NotFound("Application not found")
    if application.status in CLOSED_APPLICATION_STATUSES:
        raise BusinessRule(f"This application is already closed ({application.status})")
    application.status, application.status_note = "Withdrawn", "Withdrawn by the student"
    db.session.flush()
    audit.record("APPLICATION_WITHDRAWN", "application", application.application_id, new={"student": student.student_code},
                 branch_id=student.service_branch_id)
    return application


# ---------------------------------------------------------------- staff: scope

def _visible_branches() -> set[int] | None:
    return scope.visible_branch_ids(current_user())


def _assert_opportunity_visible(opportunity: Opportunity) -> None:
    branch_ids = _visible_branches()
    if branch_ids is not None and opportunity.branch_id is not None and opportunity.branch_id not in branch_ids:
        raise NotFound("Opportunity not found")


def _assert_branch_writable(branch_id: int | None) -> None:
    """An opportunity tied to a branch can only be created for a branch the user works at; company-wide ones need an admin."""
    branch_ids = _visible_branches()
    if branch_ids is None:
        return
    if branch_id is None or branch_id not in branch_ids:
        raise ValidationError("Choose one of your branches", {"branch_id": ["Only an admin can publish to all branches"]})


# ---------------------------------------------------------------- staff: opportunities

def list_opportunities(filters: dict, page: int, per_page: int) -> tuple[list[Opportunity], dict]:
    return paginate(career_repo.opportunities_stmt(filters, _visible_branches()), page, per_page)


def get_opportunity(opportunity_id: int) -> Opportunity:
    opportunity = career_repo.get_opportunity(opportunity_id)
    if opportunity is None:
        raise NotFound("Opportunity not found")
    _assert_opportunity_visible(opportunity)
    return opportunity


def create_opportunity(data: dict) -> Opportunity:
    _assert_branch_writable(data.get("branch_id"))
    opportunity = Opportunity(created_by=current_user().user_id, **data)
    db.session.add(opportunity)
    db.session.flush()
    db.session.refresh(opportunity)
    audit.record("OPPORTUNITY_CREATED", "opportunity", opportunity.opportunity_code,
                 new={"title": opportunity.title, "employer": opportunity.employer_name}, branch_id=opportunity.branch_id)
    return opportunity


def update_opportunity(opportunity_id: int, data: dict) -> Opportunity:
    opportunity = get_opportunity(opportunity_id)
    if opportunity.status not in EDITABLE_OPPORTUNITY_STATUSES:
        raise BusinessRule(f"An {opportunity.status} opportunity cannot be edited; put it On Hold first")
    if "branch_id" in data:
        _assert_branch_writable(data["branch_id"])
    old = {key: getattr(opportunity, key) for key in data}
    for key, value in data.items():
        setattr(opportunity, key, value)
    if opportunity.verified_by is not None:
        # A material edit needs a fresh verification (Module 23 §7)
        opportunity.status, opportunity.verified_by, opportunity.verified_at = "Verification Pending", None, None
    db.session.flush()
    db.session.refresh(opportunity)
    audit.record("OPPORTUNITY_UPDATED", "opportunity", opportunity.opportunity_code, old=old, new=data, branch_id=opportunity.branch_id)
    return opportunity


def change_opportunity_status(opportunity_id: int, status: str, verification_source: str | None) -> Opportunity:
    opportunity = get_opportunity(opportunity_id)
    user = current_user()
    if status not in OPPORTUNITY_TRANSITIONS[opportunity.status]:
        raise BusinessRule(f"An opportunity cannot move from {opportunity.status} to {status}")
    old_status = opportunity.status
    if status == "Active" and opportunity.verified_by is None:
        if opportunity.created_by == user.user_id:
            raise BusinessRule("An opportunity must be verified by someone other than its creator")
        if not verification_source:
            raise ValidationError("Say how the employer was verified", {"verification_source": ["Required to activate"]})
        opportunity.verification_source, opportunity.verified_by, opportunity.verified_at = verification_source, user.user_id, _now()
    opportunity.status = status
    db.session.flush()
    db.session.refresh(opportunity)
    audit.record("OPPORTUNITY_STATUS", "opportunity", opportunity.opportunity_code, old={"status": old_status}, new={"status": status},
                 branch_id=opportunity.branch_id)
    return opportunity


# ---------------------------------------------------------------- staff: career profiles

def list_profiles(filters: dict, page: int, per_page: int) -> tuple[list[CareerProfile], dict]:
    return paginate(career_repo.profiles_stmt(filters, _visible_branches()), page, per_page)


@dataclass
class StudentCareer:
    profile: CareerProfile
    completeness: dict
    cvs: list[CvDocument]
    applications: list[Application]
    outcomes: list[PlacementOutcome]


def get_student_career(student_id: int) -> StudentCareer:
    student = _student(student_id)
    profile = career_repo.get_profile(student.student_id)
    if profile is None:
        raise NotFound("This student has no career profile")
    cvs = career_repo.cvs_of_student(student.student_id)
    return StudentCareer(profile, completeness(profile, any(cv.review_status == "Reviewed" for cv in cvs)), cvs,
                         career_repo.applications_of_student(student.student_id), career_repo.outcomes_of_student(student.student_id))


def review_profile(student_id: int, data: dict) -> CareerProfile:
    """Readiness for referral, with an optional verification of the student's listed skills."""
    student = _student(student_id)
    profile = career_repo.get_profile(student.student_id)
    if profile is None or not profile.opted_in:
        raise BusinessRule("This student has not opted in to career support")
    old = {"readiness": profile.readiness}
    profile.readiness, profile.readiness_note = data["readiness"], data.get("note")
    profile.readiness_reviewed_by, profile.readiness_reviewed_at = current_user().user_id, _now()
    if data.get("skills"):
        by_name = {s["name"].lower(): s for s in profile.skills}
        unknown = [s["name"] for s in data["skills"] if s["name"].lower() not in by_name]
        if unknown:
            raise ValidationError("Not skills on the student's profile", {"skills": [f"Unknown: {', '.join(unknown)}"]})
        profile.skills = [{**s, "confidence": next((c["confidence"] for c in data["skills"] if c["name"].lower() == s["name"].lower()), s["confidence"])}
                          for s in profile.skills]
    db.session.flush()
    audit.record("CAREER_READINESS_REVIEWED", "career_profile", student.student_code, old=old, new={"readiness": profile.readiness},
                 reason=profile.readiness_note, branch_id=student.service_branch_id)
    return profile


def extend_support(student_id: int, support_end: date, reason: str) -> CareerProfile:
    """Super Admin / Founder extends the support period (Module 23 §2); the reason is recorded."""
    student = _student(student_id)
    profile = career_repo.get_profile(student.student_id)
    if profile is None or not profile.opted_in:
        raise BusinessRule("This student has not opted in to career support")
    if profile.support_end is not None and support_end <= profile.support_end:
        raise ValidationError("Choose a later end date", {"support_end": [f"Must be after {profile.support_end.isoformat()}"]})
    old = {"support_end": profile.support_end}
    profile.support_end, profile.support_extension_reason = support_end, reason
    db.session.flush()
    audit.record("CAREER_SUPPORT_EXTENDED", "career_profile", student.student_code, old=old, new={"support_end": support_end},
                 reason=reason, branch_id=student.service_branch_id)
    return profile


def review_cv(cv_id: int, status: str, feedback: str | None) -> CvDocument:
    cv = career_repo.get_cv(cv_id)
    if cv is None:
        raise NotFound("CV not found")
    student = _student(cv.student_id)
    if cv.review_status == "Superseded":
        raise BusinessRule("This CV version has been superseded by a newer upload")
    if status == "Changes Requested" and not feedback:
        raise ValidationError("Say what needs to change", {"feedback": ["Required when requesting changes"]})
    cv.review_status, cv.review_feedback = status, feedback
    cv.reviewed_by, cv.reviewed_at = current_user().user_id, _now()
    db.session.flush()
    audit.record("CV_REVIEWED", "cv_document", cv.cv_id, new={"status": status}, reason=feedback, branch_id=student.service_branch_id)
    student_user = _student_user(student)
    if student_user is not None:
        notify(category="Career", title=f"Your CV v{cv.version_no} was reviewed: {status}", body=feedback, link="/career",
               event_key=f"cv:{cv.cv_id}:reviewed:{status}", recipient_user_ids=[student_user], branch_id=student.service_branch_id)
    return cv


def _student_user(student: Student) -> int | None:
    user = users_repo.get_by_student_id(student.student_id)
    return user.user_id if user else None


# ---------------------------------------------------------------- staff: applications

def list_applications(filters: dict, page: int, per_page: int) -> tuple[list[Application], dict]:
    return paginate(career_repo.applications_stmt(filters, _visible_branches()), page, per_page)


def get_application(application_id: int) -> Application:
    application = career_repo.get_application(application_id)
    if application is None:
        raise NotFound("Application not found")
    _student(application.student_id)
    return application


def change_application_status(application_id: int, data: dict) -> Application:
    """Record what actually happened at the employer. Stages may be skipped; a closed application cannot change."""
    application = get_application(application_id)
    old_status = application.status
    application.status, application.status_note = data["status"], data.get("note")
    if "interview_round" in data:
        application.interview_round = data["interview_round"]
    if "interview_at" in data:
        application.interview_at = data["interview_at"]
    if data["status"] == "Interview Scheduled" and application.interview_at is None:
        raise ValidationError("Give the interview date and time", {"interview_at": ["Required when an interview is scheduled"]})
    db.session.flush()
    audit.record("APPLICATION_STATUS", "application", application.application_id, old={"status": old_status},
                 new={"status": application.status}, reason=data.get("note"), branch_id=application.student.service_branch_id)
    student_user = _student_user(application.student)
    if student_user is not None:
        notify(category="Career", title=f"{application.opportunity.title}: {application.status}", body=data.get("note"), link="/career",
               event_key=f"application:{application.application_id}:{application.status}:{application.interview_at.isoformat() if application.interview_at else ''}",
               recipient_user_ids=[student_user], branch_id=application.student.service_branch_id)
    return application


# ---------------------------------------------------------------- staff: outcomes

def list_outcomes(filters: dict, page: int, per_page: int) -> tuple[list[PlacementOutcome], dict]:
    return paginate(career_repo.outcomes_stmt(filters, _visible_branches()), page, per_page)


def record_outcome(data: dict) -> PlacementOutcome:
    student = _student(data["student_id"])
    if data.get("application_id") is not None:
        application = career_repo.get_application(data["application_id"])
        if application is None or application.student_id != student.student_id:
            raise ValidationError("Not an application of this student", {"application_id": ["Choose one of the student's applications"]})
    outcome = PlacementOutcome(recorded_by=current_user().user_id, **data)
    db.session.add(outcome)
    db.session.flush()
    audit.record("OUTCOME_RECORDED", "placement_outcome", outcome.outcome_id,
                 new={"student": student.student_code, "type": outcome.outcome_type, "employer": outcome.employer_name},
                 branch_id=student.service_branch_id)
    return outcome


def verify_outcome(outcome_id: int, decision: str, evidence_note: str) -> PlacementOutcome:
    """A second person confirms the outcome with evidence, or rejects it. Only Verified outcomes count in reports."""
    outcome = career_repo.get_outcome(outcome_id)
    if outcome is None:
        raise NotFound("Outcome not found")
    student = _student(outcome.student_id)
    if outcome.verification_status != "Pending Verification":
        raise BusinessRule(f"This outcome is already {outcome.verification_status}")
    if outcome.recorded_by == current_user().user_id:
        raise BusinessRule("An outcome must be verified by someone other than the person who recorded it")
    outcome.verification_status, outcome.evidence_note = decision, evidence_note
    outcome.verified_by, outcome.verified_at = current_user().user_id, _now()
    db.session.flush()
    audit.record("OUTCOME_VERIFIED" if decision == "Verified" else "OUTCOME_REJECTED", "placement_outcome", outcome.outcome_id,
                 new={"verification_status": decision}, reason=evidence_note, branch_id=student.service_branch_id)
    return outcome


def verified_outcome_summary() -> list[dict]:
    """What reports may count: verified outcomes and distinct students per outcome type, in the user's branches."""
    return [{"outcome_type": kind, "outcomes": total, "students": students}
            for kind, total, students in career_repo.verified_outcome_counts(_visible_branches())]


def home_summary(student_id: int) -> dict:
    """Opt-in and profile completeness for the student's home card (no opportunities or applications are loaded)."""
    profile = career_repo.get_profile(student_id)
    has_reviewed = any(cv.review_status == "Reviewed" for cv in career_repo.cvs_of_student(student_id))
    return {"opted_in": bool(profile and profile.opted_in), "profile_percent": completeness(profile, has_reviewed)["percent"]}

