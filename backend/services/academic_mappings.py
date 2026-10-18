"""Moving a student between curriculum versions (Module 14 §8, §11).

An academic mapping records the side-by-side comparison (outcomes met, previous work, remaining obligations), a migration
plan, trainer evidence and how the student accepted the change. The receiving branch's Branch Manager (or Super Admin)
approves it, never the person who asked; approving moves the enrolment (or one combo track) to the new version and records
any credited topics with their original evidence — credits count towards required learning, never as attendance or work.
Credit needs an existing approved equivalence rule between the two versions; a new rule needs the Founder / CEO or Super
Admin, independently of whoever proposed it.
"""
from datetime import datetime, timezone

from sqlalchemy import select

from config.database import db
from models import AcademicMapping, CurriculumVersion, Enrolment, EquivalenceRule, LearningCredit
from repositories import batches as batches_repo
from repositories import catalog as catalog_repo
from repositories import students as students_repo
from repositories.common import paginate
from services import approvals, audit, delivery_notices, scope
from services.context import current_user
from services.errors import BusinessRule, Conflict, Forbidden, NotFound, ValidationError
from services.notifications import notify

REQUESTERS = ("TRAINER", "BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
DECIDERS = ("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
RULE_DECIDERS = ("FOUNDER_CEO", "SUPER_ADMIN")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _version(version_id: int) -> CurriculumVersion:
    version = catalog_repo.get_curriculum_version(version_id)
    if version is None:
        raise ValidationError("Invalid request data", {"to_version_id": ["Unknown curriculum version"]})
    return version


# ---------------------------------------------------------------- equivalence rules

def request_rule(from_version_id: int, to_version_id: int, description: str) -> EquivalenceRule:
    if not current_user().has_role("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO"):
        raise Forbidden("Equivalence rules are proposed by a Branch Manager after academic review")
    source, target = _version(from_version_id), _version(to_version_id)
    if source.curriculum_version_id == target.curriculum_version_id:
        raise ValidationError("Invalid request data", {"to_version_id": ["Choose two different versions"]})
    rule = EquivalenceRule(from_version_id=source.curriculum_version_id, to_version_id=target.curriculum_version_id,
                           description=description, requested_by=current_user().user_id)
    db.session.add(rule)
    db.session.flush()
    audit.record("EQUIVALENCE_RULE_PROPOSED", "equivalence_rule", rule.rule_id,
                 new={"from": source.version_label, "to": target.version_label}, reason=description)
    for role_code, link in (("FOUNDER_CEO", "/founder/curriculum"), ("SUPER_ADMIN", "/branch/curriculum")):
        notify(category="Curriculum", title=f"Equivalence rule to approve: {source.version_label} → {target.version_label}",
               body=description, link=link, role_code=role_code, event_key=f"equivalence-rule:{rule.rule_id}:{role_code}",
               action_required=True)
    return rule


def decide_rule(rule_id: int, decision: str, note: str | None) -> EquivalenceRule:
    rule = db.session.get(EquivalenceRule, rule_id)
    if rule is None:
        raise NotFound("Equivalence rule not found")
    if not current_user().has_role(*RULE_DECIDERS):
        raise Forbidden("New equivalence rules are approved by the Founder / CEO or Super Admin")
    if rule.status != "Pending":
        raise BusinessRule(f"This rule is already {rule.status}")
    approvals.require_independent(rule.requested_by, message="An independent approver must decide: not the person who proposed the rule")
    if decision == "Rejected" and not note:
        raise ValidationError("Invalid request data", {"note": ["Give the reason for rejecting the rule"]})
    rule.status, rule.decided_by, rule.decided_at, rule.decision_note = decision, current_user().user_id, _now(), note
    db.session.flush()
    audit.record(f"EQUIVALENCE_RULE_{decision.upper()}", "equivalence_rule", rule.rule_id, reason=note)
    return rule


def list_rules(filters: dict, page: int, per_page: int):
    stmt = select(EquivalenceRule).order_by(EquivalenceRule.requested_at.desc())
    if filters.get("status"):
        stmt = stmt.where(EquivalenceRule.status == filters["status"])
    return paginate(stmt, page, per_page)


# ---------------------------------------------------------------- individual mappings

def _target_fits(enrolment: Enrolment, track, target: CurriculumVersion) -> bool:
    if track is None:
        return (target.course_id, target.component_id) == (enrolment.course_id, None)
    component = track.component
    own = (target.course_id, target.component_id) == (enrolment.course_id, component.component_id)
    reused = (component.component_course_id is not None and component.equivalence_reviewed_at is not None
              and (target.course_id, target.component_id) == (component.component_course_id, None))
    return own or reused


def _receiving_trainer(enrolment: Enrolment, to_version_id: int) -> bool:
    """A trainer who teaches a batch on the target version at the student's branch helps prepare the mapping (Module 14 §8)."""
    batches = (batches_repo.get_batch(b) for b in scope.trainer_batch_ids())
    return any(b.branch_id == enrolment.service_branch_id and b.curriculum_version_id == to_version_id for b in batches if b)


def request_mapping(enrolment_id: int, data: dict) -> AcademicMapping:
    enrolment = students_repo.get_enrolment(enrolment_id)
    if enrolment is None:
        raise NotFound("Enrolment not found")
    if not _receiving_trainer(enrolment, data["to_version_id"]):
        scope.assert_can_view_enrolment(enrolment)
    if not current_user().has_role(*REQUESTERS, branch_id=enrolment.service_branch_id):
        raise Forbidden("A trainer or the Branch Manager prepares the academic mapping")
    track = None
    if data.get("enrolment_track_id"):
        track = next((t for t in enrolment.tracks if t.enrolment_track_id == data["enrolment_track_id"]), None)
        if track is None:
            raise ValidationError("Invalid request data", {"enrolment_track_id": ["Not a track of this enrolment"]})
    target = _version(data["to_version_id"])
    if target.status not in ("Approved", "Active"):
        raise BusinessRule(f"{target.version_label} is {target.status}; map to an Approved or Active version")
    if not _target_fits(enrolment, track, target):
        raise ValidationError("Invalid request data", {"to_version_id": ["Not a version of this course or track"]})
    current_id = track.curriculum_version_id if track else enrolment.curriculum_version_id
    if current_id == target.curriculum_version_id:
        raise BusinessRule("The student already follows this version")
    credits = data.get("credits") or []
    rule = None
    if credits:
        rule = db.session.get(EquivalenceRule, data.get("rule_id") or 0)
        if rule is None or rule.status != "Approved" or (rule.from_version_id, rule.to_version_id) != (current_id, target.curriculum_version_id):
            raise BusinessRule("Credit needs an approved equivalence rule from the student's version to the new one")
        target_topics = {t.topic_id for m in target.modules for t in m.topics}
        if any(c["topic_id"] not in target_topics for c in credits):
            raise ValidationError("Invalid request data", {"credits": ["Credited topics must belong to the new version"]})
    if db.session.execute(select(AcademicMapping).where(AcademicMapping.enrolment_id == enrolment_id,
                                                        AcademicMapping.status == "Pending")).first():
        raise Conflict("This enrolment already has a mapping waiting for a decision")
    mapping = AcademicMapping(enrolment_id=enrolment_id, enrolment_track_id=track.enrolment_track_id if track else None,
                              from_version_id=current_id, to_version_id=target.curriculum_version_id,
                              rule_id=rule.rule_id if rule else None, comparison=data["comparison"], migration_plan=data["migration_plan"],
                              trainer_evidence=data.get("trainer_evidence"), proposed_credits=credits,
                              requested_by=current_user().user_id)
    db.session.add(mapping)
    db.session.flush()
    audit.record("ACADEMIC_MAPPING_REQUESTED", "enrolment", enrolment.enrolment_code,
                 new={"mapping_id": mapping.mapping_id, "to": target.version_label, "credits": len(credits)},
                 branch_id=enrolment.service_branch_id)
    notify(category="Curriculum", title=f"Academic mapping to approve: {enrolment.enrolment_code} → {target.version_label}",
           body=data["comparison"][:300], link="/branch/curriculum", role_code="BRANCH_MANAGER",
           branch_id=enrolment.service_branch_id, event_key=f"academic-mapping:{mapping.mapping_id}", action_required=True)
    return mapping


def decide_mapping(mapping_id: int, decision: str, note: str | None, student_acceptance: str | None) -> AcademicMapping:
    mapping = db.session.get(AcademicMapping, mapping_id)
    if mapping is None:
        raise NotFound("Academic mapping not found")
    enrolment = students_repo.get_enrolment(mapping.enrolment_id)
    scope.require_branch(enrolment.service_branch_id)
    if not current_user().has_role(*DECIDERS, branch_id=enrolment.service_branch_id):
        raise Forbidden("The receiving branch's Branch Manager approves the academic mapping")
    if mapping.status != "Pending":
        raise BusinessRule(f"This mapping is already {mapping.status}")
    approvals.require_independent(mapping.requested_by, message="An independent reviewer must decide: not the person who prepared the mapping",
                                  requester=mapping.requested_by)
    if decision == "Rejected" and not note:
        raise ValidationError("Invalid request data", {"note": ["Give the reason for rejecting the mapping"]})
    if decision == "Approved" and not student_acceptance:
        raise ValidationError("Invalid request data", {"student_acceptance": ["Record how the student accepted the change"]})

    mapping.status, mapping.decided_by, mapping.decided_at, mapping.decision_note = decision, current_user().user_id, _now(), note
    mapping.student_acceptance = student_acceptance
    if decision == "Approved":
        if mapping.enrolment_track_id:
            track = next(t for t in enrolment.tracks if t.enrolment_track_id == mapping.enrolment_track_id)
            track.curriculum_version_id = mapping.to_version_id
        else:
            enrolment.curriculum_version_id = mapping.to_version_id
        for credit in mapping.proposed_credits:
            db.session.add(LearningCredit(enrolment_id=enrolment.enrolment_id, topic_id=credit["topic_id"], mapping_id=mapping.mapping_id,
                                          original_evidence=credit["original_evidence"], rule_id=mapping.rule_id,
                                          reviewed_by=current_user().user_id))
        db.session.flush()
        delivery_notices.notify_student(enrolment.student_id, title=f"Your curriculum version changed: {enrolment.course.title}",
                                        body=mapping.migration_plan[:300], event_key=f"academic-mapping-applied:{mapping.mapping_id}",
                                        link="/my-courses", branch_id=enrolment.service_branch_id)
    db.session.flush()
    db.session.refresh(mapping)
    audit.record(f"ACADEMIC_MAPPING_{decision.upper()}", "enrolment", enrolment.enrolment_code,
                 old={"version_id": mapping.from_version_id}, new={"version_id": mapping.to_version_id, "decision": decision},
                 reason=note, branch_id=enrolment.service_branch_id)
    return mapping


def list_mappings(filters: dict, page: int, per_page: int):
    stmt = select(AcademicMapping).join(Enrolment, Enrolment.enrolment_id == AcademicMapping.enrolment_id).order_by(AcademicMapping.requested_at.desc())
    branch_ids = scope.visible_branch_ids()
    if branch_ids is not None:
        stmt = stmt.where(Enrolment.service_branch_id.in_(branch_ids))
    for key in ("status", "enrolment_id"):
        if filters.get(key):
            stmt = stmt.where(getattr(AcademicMapping, key) == filters[key])
    return paginate(stmt, page, per_page)
