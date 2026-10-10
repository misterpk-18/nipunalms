from flask import request

from controllers.common import Validator, created, json_body, no_content, ok, require_changes
from models.enums import CURRICULUM_STATUSES
from services import curriculum as curriculum_service
from services.errors import ValidationError

TOPIC_CLASSES = ("Required", "Recommended", "Optional")


def _summary(version) -> dict | None:
    return version.to_summary() if version else None


def _version(detail, *, full: bool = False) -> dict:
    version = detail.version
    data = {
        **version.to_summary(),
        "course": detail.course.to_summary(),
        "component": detail.component.to_dict() if detail.component else None,
        "approved_at": version.approved_at,
        "created_at": version.created_at,
        "counts": detail.counts,
        "usage": detail.usage,
    }
    if full:
        data["modules"] = [m.to_dict() for m in version.modules]
        data["events"] = [e.to_dict() for e in detail.events]
        data["blockers"] = detail.blockers
        data.update(curriculum_service.version_extras(version))
    return data


def overview():
    return ok([{
        "course": row.course.to_summary() | {"is_combo": row.course.is_combo},
        "component": row.component.to_dict() if row.component else None,
        "active_version": _summary(row.active),
        "latest_version": _summary(row.latest),
        "readiness": row.readiness,
        "waiting_batches": row.waiting_batches,
        "borrowed_from": row.borrowed_from.to_summary() if row.borrowed_from else None,
    } for row in curriculum_service.overview()])


def list_versions():
    v = Validator(request.args.to_dict())
    v.integer("course_id", min_value=1)
    v.integer("component_id", min_value=1)
    v.boolean("whole_course", default=False)  # only versions of the course as a whole, not of a combo track
    v.boolean("with_content", default=False)  # include modules and topics (for topic pickers)
    v.choice("status", CURRICULUM_STATUSES)
    filters = v.validate()
    if filters.pop("whole_course"):
        filters["component_id"] = None
    with_content = filters.pop("with_content")
    return ok([{**_version(d), **({"modules": [m.to_dict() for m in d.version.modules]} if with_content else {})}
               for d in curriculum_service.list_versions(filters)])


def get_version(curriculum_version_id: int):
    return ok(_version(curriculum_service.get_version_detail(curriculum_version_id), full=True))


def create_version():
    v = Validator(json_body())
    v.integer("course_id", required=True, min_value=1)
    v.integer("component_id", nullable=True, min_value=1)
    v.string("version_label", required=True, max_length=100)
    v.integer("copy_from_version_id", nullable=True, min_value=1)
    version = curriculum_service.create_version(v.validate())
    return created(_version(curriculum_service.get_version_detail(version.curriculum_version_id), full=True))


def update_version(curriculum_version_id: int):
    v = Validator(json_body())
    v.string("version_label", required=True, max_length=100)
    curriculum_service.update_version(curriculum_version_id, v.validate()["version_label"])
    return get_version(curriculum_version_id)


def delete_version(curriculum_version_id: int):
    curriculum_service.delete_version(curriculum_version_id)
    return no_content()


def _after(curriculum_version_id: int, extra: dict | None = None):
    detail = _version(curriculum_service.get_version_detail(curriculum_version_id), full=True)
    return ok({**detail, **(extra or {})})


def submit(curriculum_version_id: int):
    curriculum_service.submit(curriculum_version_id)
    return _after(curriculum_version_id)


def return_to_draft(curriculum_version_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, max_length=500)
    curriculum_service.return_to_draft(curriculum_version_id, v.validate()["reason"])
    return _after(curriculum_version_id)


def approve(curriculum_version_id: int):
    curriculum_service.approve(curriculum_version_id)
    return _after(curriculum_version_id)


def activate(curriculum_version_id: int):
    _, released = curriculum_service.activate(curriculum_version_id)
    return _after(curriculum_version_id, {"released": released})


def retire(curriculum_version_id: int):
    v = Validator(json_body())
    v.string("reason", nullable=True, max_length=500)
    curriculum_service.retire(curriculum_version_id, v.validate().get("reason"))
    return _after(curriculum_version_id)


# ---------------------------------------------------------------- modules and topics (Draft only)

def add_module(curriculum_version_id: int):
    v = Validator(json_body())
    v.string("title", required=True, max_length=200)
    v.string("title_te", nullable=True, max_length=300)
    v.integer("position", min_value=1)
    data = v.validate()
    module = curriculum_service.add_module(curriculum_version_id, data["title"], data.get("title_te"), data.get("position"))
    return created(module.to_dict())


def update_module(module_id: int):
    v = Validator(json_body())
    v.string("title", max_length=200)
    v.string("title_te", nullable=True, max_length=300)
    v.integer("position", min_value=1)
    return ok(curriculum_service.update_module(module_id, require_changes(v.validate())).to_dict())


def delete_module(module_id: int):
    curriculum_service.delete_module(module_id)
    return no_content()


def _topic_rules(v: Validator, *, creating: bool) -> None:
    """Module 14 §2: outcome, class, estimated minutes, progress weight, evidence and activities of a topic."""
    v.string("title", required=creating, max_length=200)
    v.string("title_te", nullable=True, max_length=300)
    v.boolean("is_required")
    v.choice("topic_class", TOPIC_CLASSES)
    v.string("outcome", nullable=True, max_length=2000)
    v.integer("instructional_minutes", nullable=True, min_value=0)
    v.integer("independent_minutes", nullable=True, min_value=0)
    v.decimal("weight", nullable=True, min_value=0)
    v.string("evidence", nullable=True, max_length=2000)
    v.string("activities", nullable=True, max_length=2000)
    v.integer("position", min_value=1)


def add_topic(module_id: int):
    v = Validator(json_body())
    _topic_rules(v, creating=True)
    return created(curriculum_service.add_topic(module_id, v.validate()).to_dict())


def update_topic(topic_id: int):
    v = Validator(json_body())
    _topic_rules(v, creating=False)
    v.int_list("depends_on", min_value=1)  # topics of the same version this one builds on
    return ok(curriculum_service.update_topic(topic_id, require_changes(v.validate())).to_dict())


# ---------------------------------------------------------------- Module 14: hours, profile, required assessments, combos

def verify_hours(curriculum_version_id: int):
    curriculum_service.verify_hours(curriculum_version_id)
    return get_version(curriculum_version_id)


def set_completion_profile(curriculum_version_id: int):
    v = Validator(json_body())
    v.decimal("attendance_minimum_pct", required=True, min_value=0)
    v.decimal("pass_mark_pct", required=True, min_value=0)
    v.string("recovery_rule", required=True, max_length=1000)
    v.string("reassessment_rule", required=True, max_length=1000)
    data = v.validate()
    for key in ("attendance_minimum_pct", "pass_mark_pct"):
        if data[key] > 100:
            raise ValidationError("Invalid request data", {key: ["At most 100"]})
        data[key] = float(data[key])
    curriculum_service.set_completion_profile(curriculum_version_id, data)
    return get_version(curriculum_version_id)


def add_requirement(curriculum_version_id: int):
    v = Validator(json_body())
    v.choice("kind", ("Assignment", "Test"), required=True)
    v.string("title", required=True, max_length=200)
    v.string("outcome", required=True, max_length=2000)
    v.decimal("weight", required=True, min_value=0)
    v.string("pass_rule", required=True, max_length=1000)
    v.boolean("counts_for_completion", default=True)
    v.integer("module_id", nullable=True, min_value=1)
    v.integer("topic_id", nullable=True, min_value=1)
    return created(curriculum_service.add_requirement(curriculum_version_id, v.validate()).to_dict())


def delete_requirement(requirement_id: int):
    curriculum_service.delete_requirement(requirement_id)
    return no_content()


def pin_component(curriculum_version_id: int):
    v = Validator(json_body())
    v.integer("component_id", required=True, min_value=1)
    v.integer("component_version_id", required=True, min_value=1)
    data = v.validate()
    curriculum_service.pin_component(curriculum_version_id, data["component_id"], data["component_version_id"])
    return get_version(curriculum_version_id)


def review_equivalence(component_id: int):
    v = Validator(json_body())
    v.string("note", required=True, max_length=2000)
    return ok(curriculum_service.review_equivalence(component_id, v.validate()["note"]).to_dict())


def delete_topic(topic_id: int):
    curriculum_service.delete_topic(topic_id)
    return no_content()
