from flask import request, send_file

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated, require_changes
from models.career import (
    APPLICATION_STATUSES, EMPLOYMENT_TYPES, OPPORTUNITY_STATUSES, OPPORTUNITY_WORK_MODES, OUTCOME_TYPES, READINESS_LEVELS,
    SKILL_CONFIDENCE, WORK_MODES,
)
from services import career as career_service

NO_GUARANTEE = "Placement / career assistance only — no guaranteed placement."


def _profile(overview: career_service.CareerOverview) -> dict:
    if overview.profile is not None:
        return overview.profile.to_dict(overview.completeness)
    return {
        "student": overview.student.to_summary(), "opted_in": False, "opted_in_at": None, "support_start": None, "support_end": None,
        "support_extension_reason": None, "preferred_roles": [], "preferred_locations": [], "work_mode": None, "qualification": None,
        "graduation_year": None, "experience_level": None, "skills": [], "portfolio_url": None, "availability": None,
        "sharing_consent": False, "sharing_consent_at": None, "readiness": "Not Assessed", "readiness_note": None,
        "readiness_reviewed_at": None, "completeness": overview.completeness,
    }


def _student_outcome(outcome) -> dict:
    """Students see what was recorded and whether it is verified, not the internal evidence note."""
    return {**outcome.to_dict(), "evidence_note": None}


# ---------------------------------------------------------------- student

def overview():
    o = career_service.overview()
    return ok({
        "notice": NO_GUARANTEE,
        "profile": _profile(o),
        "cvs": [cv.to_dict() for cv in o.cvs],
        "opportunities": [{**op.to_student_dict(), "applied": op.opportunity_id in o.applied_opportunity_ids} for op in o.opportunities],
        "applications": [{**a.to_dict(), "opportunity": _opportunity_of(a)} for a in o.applications],
        "outcomes": [_student_outcome(x) for x in o.outcomes],
        "next_action": o.next_action,
    })


def _opportunity_of(application) -> dict:
    return {**application.opportunity.to_summary(), "location": application.opportunity.location,
            "employment_type": application.opportunity.employment_type}


def update_profile():
    v = Validator(json_body())
    v.boolean("opted_in")
    v.string_list("preferred_roles")
    v.string_list("preferred_locations")
    v.choice("work_mode", WORK_MODES, nullable=True)
    v.string("qualification", nullable=True, max_length=200)
    v.integer("graduation_year", nullable=True, min_value=1990, max_value=2100)
    v.choice("experience_level", ("Fresher", "Experienced"), nullable=True)
    v.string_list("skills")
    v.string("portfolio_url", nullable=True, max_length=500, pattern=r"https?://\S+", pattern_message="Must be a web link starting with http:// or https://")
    v.string("availability", nullable=True, max_length=200)
    career_service.update_profile(require_changes(v.validate()))
    return overview()


def set_consent():
    v = Validator(json_body())
    v.boolean("sharing_consent", required=True)
    career_service.set_consent(v.validate()["sharing_consent"])
    return overview()


def upload_cv():
    v = Validator({"label": request.form.get("label") or None})
    v.string("label", nullable=True, max_length=150)
    cv = career_service.upload_cv(request.files.get("file"), v.validate().get("label"))
    return created(cv.to_dict())


def download_cv(cv_id: int):
    cv, path = career_service.download_cv(cv_id)
    return send_file(path, as_attachment=True, download_name=cv.original_filename, mimetype=cv.mime_type)


def apply(opportunity_id: int):
    return created(career_service.apply(opportunity_id).to_dict())


def withdraw(application_id: int):
    return ok(career_service.withdraw(application_id).to_dict())


# ---------------------------------------------------------------- staff: opportunities

def _opportunity_rules(v: Validator, *, required: bool) -> None:
    v.string("title", required=required, max_length=200)
    v.string("employer_name", required=required, max_length=200)
    v.string("employer_source", nullable=True, max_length=300)
    v.choice("employment_type", EMPLOYMENT_TYPES)
    v.choice("work_mode", OPPORTUNITY_WORK_MODES)
    v.string("location", nullable=True, max_length=200)
    v.string("description", nullable=True, max_length=4000)
    v.string_list("required_skills")
    v.integer("course_id", nullable=True, min_value=1)
    v.integer("branch_id", nullable=True, min_value=1)
    v.string("compensation_text", max_length=200)
    v.integer("openings", nullable=True, min_value=1)
    v.date("closing_date", nullable=True)


def list_opportunities():
    v = Validator(request.args.to_dict())
    v.choice("status", OPPORTUNITY_STATUSES)
    v.integer("course_id", min_value=1)
    v.string("q", max_length=100)
    page, per_page = get_page_params()
    items, meta = career_service.list_opportunities(v.validate(), page, per_page)
    return paginated([o.to_dict() for o in items], meta)


def get_opportunity(opportunity_id: int):
    return ok(career_service.get_opportunity(opportunity_id).to_dict())


def create_opportunity():
    v = Validator(json_body())
    _opportunity_rules(v, required=True)
    return created(career_service.create_opportunity(v.validate()).to_dict())


def update_opportunity(opportunity_id: int):
    v = Validator(json_body())
    _opportunity_rules(v, required=False)
    return ok(career_service.update_opportunity(opportunity_id, require_changes(v.validate())).to_dict())


def change_opportunity_status(opportunity_id: int):
    v = Validator(json_body())
    v.choice("status", OPPORTUNITY_STATUSES, required=True)
    v.string("verification_source", nullable=True, max_length=300)
    data = v.validate()
    return ok(career_service.change_opportunity_status(opportunity_id, data["status"], data.get("verification_source")).to_dict())


# ---------------------------------------------------------------- staff: profiles, CVs, applications, outcomes

def list_profiles():
    v = Validator(request.args.to_dict())
    v.boolean("opted_in")
    v.choice("readiness", READINESS_LEVELS)
    v.integer("branch_id", min_value=1)
    v.string("q", max_length=100)
    page, per_page = get_page_params()
    items, meta = career_service.list_profiles(v.validate(), page, per_page)
    return paginated([p.to_dict({}) for p in items], meta)


def get_student_career(student_id: int):
    c = career_service.get_student_career(student_id)
    return ok({
        "profile": c.profile.to_dict(c.completeness),
        "cvs": [cv.to_dict() for cv in c.cvs],
        "applications": [a.to_dict() for a in c.applications],
        "outcomes": [o.to_dict() for o in c.outcomes],
    })


def review_profile(student_id: int):
    v = Validator(json_body())
    v.choice("readiness", READINESS_LEVELS, required=True)
    v.string("note", nullable=True, max_length=2000)

    def skill(item: Validator) -> None:
        item.string("name", required=True, max_length=100)
        item.choice("confidence", SKILL_CONFIDENCE, required=True)

    v.list_of("skills", skill)
    profile = career_service.review_profile(student_id, v.validate())
    return ok(profile.to_dict({}))


def extend_support(student_id: int):
    v = Validator(json_body())
    v.date("support_end", required=True)
    v.string("reason", required=True, max_length=1000)
    data = v.validate()
    return ok(career_service.extend_support(student_id, data["support_end"], data["reason"]).to_dict({}))


def review_cv(cv_id: int):
    v = Validator(json_body())
    v.choice("status", ("Reviewed", "Changes Requested"), required=True)
    v.string("feedback", nullable=True, max_length=2000)
    data = v.validate()
    return ok(career_service.review_cv(cv_id, data["status"], data.get("feedback")).to_dict())


def list_applications():
    v = Validator(request.args.to_dict())
    v.choice("status", APPLICATION_STATUSES)
    v.boolean("open")
    v.integer("student_id", min_value=1)
    v.integer("opportunity_id", min_value=1)
    page, per_page = get_page_params()
    items, meta = career_service.list_applications(v.validate(), page, per_page)
    return paginated([a.to_dict(include_events=True) for a in items], meta)


def get_application(application_id: int):
    return ok(career_service.get_application(application_id).to_dict(include_events=True))


def change_application_status(application_id: int):
    v = Validator(json_body())
    v.choice("status", APPLICATION_STATUSES, required=True)
    v.string("note", nullable=True, max_length=2000)
    v.string("interview_round", nullable=True, max_length=100)
    v.datetime("interview_at", nullable=True)
    return ok(career_service.change_application_status(application_id, v.validate()).to_dict(include_events=True))


def list_outcomes():
    v = Validator(request.args.to_dict())
    v.integer("student_id", min_value=1)
    v.choice("verification_status", ("Pending Verification", "Verified", "Rejected"))
    page, per_page = get_page_params()
    items, meta = career_service.list_outcomes(v.validate(), page, per_page)
    return paginated([o.to_dict() for o in items], meta)


def record_outcome():
    v = Validator(json_body())
    v.integer("student_id", required=True, min_value=1)
    v.integer("application_id", nullable=True, min_value=1)
    v.choice("outcome_type", OUTCOME_TYPES, required=True)
    v.string("employer_name", required=True, max_length=200)
    v.string("role_title", required=True, max_length=200)
    v.date("event_date", required=True)
    v.string("compensation_text", nullable=True, max_length=200)
    return created(career_service.record_outcome(v.validate()).to_dict())


def verify_outcome(outcome_id: int):
    v = Validator(json_body())
    v.choice("decision", ("Verified", "Rejected"), required=True)
    v.string("evidence_note", required=True, max_length=2000)
    data = v.validate()
    return ok(career_service.verify_outcome(outcome_id, data["decision"], data["evidence_note"]).to_dict())


def outcome_summary():
    return ok(career_service.verified_outcome_summary())
