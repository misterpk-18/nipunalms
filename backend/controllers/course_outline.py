from controllers.common import Validator, created, get_page_params, json_body, no_content, ok, paginated, require_changes
from services import course_library, course_outline
from services.errors import ValidationError

TOPIC_CLASSES = ("Required", "Recommended", "Optional")


def list_courses():
    return ok(course_outline.list_courses())


def get_outline(course_id: int):
    return ok(course_outline.get_outline(course_id))


def _after(course_id: int):
    return get_outline(course_id)


def add_module(course_id: int):
    v = Validator(json_body())
    v.string("title", required=True, max_length=200)
    v.string("title_te", nullable=True, max_length=300)
    v.integer("position", min_value=1)
    v.integer("component_id", nullable=True, min_value=1)  # a combo track's own outline
    data = v.validate()
    module = course_outline.add_module(course_id, data["title"], data.get("title_te"), data.get("position"), data.get("component_id"))
    return created(module.to_dict())


def update_module(module_id: int):
    v = Validator(json_body())
    v.string("title", max_length=200)
    v.string("title_te", nullable=True, max_length=300)
    v.integer("position", min_value=1)
    return ok(course_outline.update_module(module_id, require_changes(v.validate())).to_dict())


def delete_module(module_id: int):
    course_outline.delete_module(module_id)
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
    return created(course_outline.add_topic(module_id, v.validate()).to_dict())


def update_topic(topic_id: int):
    v = Validator(json_body())
    _topic_rules(v, creating=False)
    v.int_list("depends_on", min_value=1)  # topics of the same outline this one builds on
    return ok(course_outline.update_topic(topic_id, require_changes(v.validate())).to_dict())


def delete_topic(topic_id: int):
    course_outline.delete_topic(topic_id)
    return no_content()


def verify_hours(course_id: int):
    course_outline.verify_hours(course_id)
    return _after(course_id)


def set_completion_profile(course_id: int):
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
    course_outline.set_completion_profile(course_id, data)
    return _after(course_id)


def add_requirement(course_id: int):
    v = Validator(json_body())
    v.choice("kind", ("Assignment", "Test"), required=True)
    v.string("title", required=True, max_length=200)
    v.string("outcome", required=True, max_length=2000)
    v.decimal("weight", required=True, min_value=0)
    v.string("pass_rule", required=True, max_length=1000)
    v.boolean("counts_for_completion", default=True)
    v.integer("module_id", nullable=True, min_value=1)
    v.integer("topic_id", nullable=True, min_value=1)
    return created(course_outline.add_requirement(course_id, v.validate()).to_dict())


def delete_requirement(requirement_id: int):
    course_outline.delete_requirement(requirement_id)
    return no_content()


def pin_track(course_id: int):
    v = Validator(json_body())
    v.integer("component_id", required=True, min_value=1)
    v.integer("pinned_course_id", nullable=True, min_value=1)
    data = v.validate()
    course_outline.pin_track(course_id, data["component_id"], data.get("pinned_course_id"))
    return _after(course_id)


def review_equivalence(component_id: int):
    v = Validator(json_body())
    v.string("note", required=True, max_length=2000)
    return ok(course_outline.review_equivalence(component_id, v.validate()["note"]).to_dict())


# ---------------------------------------------------------------- reusable module library

def list_library():
    page, per_page = get_page_params()
    items, meta = course_library.list_library(page, per_page)
    return paginated([m.to_dict() for m in items], meta)


def save_to_library(module_id: int):
    return created(course_library.save_to_library(module_id).to_dict())


def propose_library_version(library_module_id: int):
    v = Validator(json_body())
    v.integer("module_id", required=True, min_value=1)
    v.string("change_note", required=True, max_length=1000)
    data = v.validate()
    return created(course_library.propose_version(library_module_id, data["module_id"], data["change_note"]).to_dict())


def insert_library_module(course_id: int):
    v = Validator(json_body())
    v.integer("library_version_id", required=True, min_value=1)
    v.integer("component_id", nullable=True, min_value=1)
    data = v.validate()
    return created(course_library.insert_into(course_id, data["library_version_id"], data.get("component_id")).to_dict())
