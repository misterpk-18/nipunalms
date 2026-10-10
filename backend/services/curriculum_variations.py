"""Branch and batch academic variations (Module 14 §7). Local examples, equivalent exercises, teaching language and
sequencing within the approved outcomes are recorded and approved by the Branch Manager (a Branch Manager's own entry is
approved as it is recorded). Removing or constraining a required topic because a trainer, tool or facility is unavailable
needs a recorded constraint and a remedial plan approved by the Founder / CEO or Super Admin."""
from datetime import datetime, timezone

from sqlalchemy import select

from config.database import db
from models import CurriculumVariation
from repositories import batches as batches_repo
from repositories import catalog as catalog_repo
from repositories.common import paginate
from services import approvals, audit, scope
from services.context import current_user
from services.errors import BusinessRule, Forbidden, NotFound, ValidationError
from services.notifications import notify

CONSTRAINT = "Required topic constraint"
LOCAL_APPROVERS = ("BRANCH_MANAGER", "SUPER_ADMIN")
CONSTRAINT_APPROVERS = ("FOUNDER_CEO", "SUPER_ADMIN")


def create(data: dict) -> CurriculumVariation:
    user = current_user()
    branch_id = data["branch_id"]
    scope.require_branch(branch_id)
    if not user.has_role("BRANCH_MANAGER", "SUPER_ADMIN", branch_id=branch_id):
        raise Forbidden("Variations are recorded by the branch's Branch Manager")
    version = catalog_repo.get_curriculum_version(data["curriculum_version_id"])
    if version is None or version.status not in ("Approved", "Active"):
        raise ValidationError("Invalid request data", {"curriculum_version_id": ["An Approved or Active curriculum version"]})
    if data.get("batch_id"):
        batch = batches_repo.get_batch(data["batch_id"])
        if batch is None or batch.branch_id != branch_id or batch.curriculum_version_id != version.curriculum_version_id:
            raise ValidationError("Invalid request data", {"batch_id": ["A batch of this branch on this version"]})
    if data.get("topic_id"):
        topic = catalog_repo.get_topic(data["topic_id"])
        if topic is None or topic.module.curriculum_version_id != version.curriculum_version_id:
            raise ValidationError("Invalid request data", {"topic_id": ["A topic of this version"]})
        if data["kind"] == CONSTRAINT and topic.topic_class != "Required":
            raise ValidationError("Invalid request data", {"topic_id": ["A constraint applies to a required topic"]})
    if data["kind"] == CONSTRAINT and not (data.get("topic_id") and data.get("remedial_plan")):
        raise ValidationError("Invalid request data", {"remedial_plan": ["Name the required topic and the remedial delivery plan"]})
    variation = CurriculumVariation(requested_by=user.user_id, **data)
    approved_now = data["kind"] != CONSTRAINT and user.has_role(*LOCAL_APPROVERS, branch_id=branch_id)
    if approved_now:
        variation.status, variation.decided_by, variation.decided_at = "Approved", user.user_id, datetime.now(timezone.utc)
    db.session.add(variation)
    db.session.flush()
    audit.record("CURRICULUM_VARIATION_" + ("APPROVED" if approved_now else "PROPOSED"), "curriculum_variation", variation.variation_id,
                 new={"kind": variation.kind, "version_id": version.curriculum_version_id}, reason=variation.description, branch_id=branch_id)
    if not approved_now:
        roles = CONSTRAINT_APPROVERS if variation.kind == CONSTRAINT else ("BRANCH_MANAGER",)
        for role_code in roles:
            notify(category="Curriculum", title=f"Curriculum variation to decide: {variation.kind}", body=variation.description[:300],
                   link="/branch/curriculum", role_code=role_code, branch_id=branch_id,
                   event_key=f"curriculum-variation:{variation.variation_id}:{role_code}", action_required=True)
    return variation


def decide(variation_id: int, decision: str, note: str | None) -> CurriculumVariation:
    variation = db.session.get(CurriculumVariation, variation_id)
    if variation is None:
        raise NotFound("Variation not found")
    scope.require_branch(variation.branch_id)
    approvers = CONSTRAINT_APPROVERS if variation.kind == CONSTRAINT else LOCAL_APPROVERS
    if not current_user().has_role(*approvers, branch_id=variation.branch_id):
        raise Forbidden("A required-topic constraint is decided by the Founder / CEO or Super Admin; other variations by the Branch Manager")
    if variation.status != "Pending":
        raise BusinessRule(f"This variation is already {variation.status}")
    approvals.require_independent(variation.requested_by, message="An independent approver must decide: not the person who recorded it",
                                  requester=variation.requested_by)
    if decision == "Rejected" and not note:
        raise ValidationError("Invalid request data", {"note": ["Give the reason for rejecting the variation"]})
    variation.status, variation.decided_by, variation.decided_at = decision, current_user().user_id, datetime.now(timezone.utc)
    variation.decision_note = note
    db.session.flush()
    audit.record(f"CURRICULUM_VARIATION_{decision.upper()}", "curriculum_variation", variation.variation_id, reason=note,
                 branch_id=variation.branch_id)
    return variation


def list_variations(filters: dict, page: int, per_page: int):
    stmt = select(CurriculumVariation).order_by(CurriculumVariation.requested_at.desc())
    branch_ids = scope.visible_branch_ids()
    if branch_ids is not None:
        stmt = stmt.where(CurriculumVariation.branch_id.in_(branch_ids | {s.branch_id for s in current_user().scopes if s.branch_id}))
    for key in ("curriculum_version_id", "branch_id", "status"):
        if filters.get(key):
            stmt = stmt.where(getattr(CurriculumVariation, key) == filters[key])
    return paginate(stmt, page, per_page)
