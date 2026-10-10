"""Module 14 records: academic mappings and credits, equivalence rules, branch variations, library."""
from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated
from models.certificates import APPROVAL_STATUSES
from services import academic_mappings, curriculum_library, curriculum_variations

VARIATION_KINDS = ("Local example", "Equivalent exercise", "Teaching language", "Sequencing", "Required topic constraint")


def _decision(*extra: str) -> dict:
    v = Validator(json_body())
    v.choice("decision", ("Approved", "Rejected"), required=True)
    v.string("note", nullable=True, max_length=1000)
    for field in extra:
        v.string(field, nullable=True, max_length=2000)
    return v.validate()


def _status_filter(*ints: str) -> dict:
    v = Validator(request.args.to_dict())
    v.choice("status", APPROVAL_STATUSES)
    for field in ints:
        v.integer(field, min_value=1)
    return v.validate()


# ---------------------------------------------------------------- equivalence rules

def request_rule():
    v = Validator(json_body())
    v.integer("from_version_id", required=True, min_value=1)
    v.integer("to_version_id", required=True, min_value=1)
    v.string("description", required=True, max_length=2000)
    data = v.validate()
    return created(academic_mappings.request_rule(data["from_version_id"], data["to_version_id"], data["description"]).to_dict())


def list_rules():
    page, per_page = get_page_params()
    items, meta = academic_mappings.list_rules(_status_filter(), page, per_page)
    return paginated([r.to_dict() for r in items], meta)


def decide_rule(rule_id: int):
    data = _decision()
    return ok(academic_mappings.decide_rule(rule_id, data["decision"], data.get("note")).to_dict())


# ---------------------------------------------------------------- academic mappings

def request_mapping(enrolment_id: int):
    v = Validator(json_body())
    v.integer("to_version_id", required=True, min_value=1)
    v.integer("enrolment_track_id", nullable=True, min_value=1)
    v.string("comparison", required=True, max_length=5000)
    v.string("migration_plan", required=True, max_length=5000)
    v.string("trainer_evidence", nullable=True, max_length=5000)
    v.integer("rule_id", nullable=True, min_value=1)

    def credit(c: Validator) -> None:
        c.integer("topic_id", required=True, min_value=1)
        c.string("original_evidence", required=True, max_length=2000)

    v.list_of("credits", credit)
    return created(academic_mappings.request_mapping(enrolment_id, v.validate()).to_dict())


def list_mappings():
    page, per_page = get_page_params()
    items, meta = academic_mappings.list_mappings(_status_filter("enrolment_id"), page, per_page)
    return paginated([m.to_dict() for m in items], meta)


def decide_mapping(mapping_id: int):
    data = _decision("student_acceptance")
    return ok(academic_mappings.decide_mapping(mapping_id, data["decision"], data.get("note"), data.get("student_acceptance")).to_dict())


# ---------------------------------------------------------------- variations

def create_variation():
    v = Validator(json_body())
    v.integer("curriculum_version_id", required=True, min_value=1)
    v.integer("branch_id", required=True, min_value=1)
    v.integer("batch_id", nullable=True, min_value=1)
    v.integer("topic_id", nullable=True, min_value=1)
    v.choice("kind", VARIATION_KINDS, required=True)
    v.string("description", required=True, max_length=2000)
    v.string("remedial_plan", nullable=True, max_length=2000)
    return created(curriculum_variations.create(v.validate()).to_dict())


def list_variations():
    page, per_page = get_page_params()
    items, meta = curriculum_variations.list_variations(_status_filter("curriculum_version_id", "branch_id"), page, per_page)
    return paginated([x.to_dict() for x in items], meta)


def decide_variation(variation_id: int):
    data = _decision()
    return ok(curriculum_variations.decide(variation_id, data["decision"], data.get("note")).to_dict())


# ---------------------------------------------------------------- library

def list_library():
    page, per_page = get_page_params()
    items, meta = curriculum_library.list_library(page, per_page)
    return paginated([m.to_dict() for m in items], meta)


def save_to_library(module_id: int):
    return created(curriculum_library.save_to_library(module_id).to_dict())


def propose_library_version(library_module_id: int):
    v = Validator(json_body())
    v.integer("module_id", required=True, min_value=1)
    v.string("change_note", required=True, max_length=1000)
    data = v.validate()
    return created(curriculum_library.propose_version(library_module_id, data["module_id"], data["change_note"]).to_dict())


def decide_library_version(library_version_id: int):
    v = Validator(json_body())
    v.choice("decision", ("Approved", "Rejected"), required=True)
    return ok(curriculum_library.decide_version(library_version_id, v.validate()["decision"]).to_dict())


def insert_library_module(curriculum_version_id: int):
    v = Validator(json_body())
    v.integer("library_version_id", required=True, min_value=1)
    return created(curriculum_library.insert_into(curriculum_version_id, v.validate()["library_version_id"]).to_dict())
