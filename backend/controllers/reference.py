from flask import request

from controllers.common import Validator, ok
from services import reference as reference_service


def list_branches():
    return ok([b.to_dict() for b in reference_service.list_branches()])


def list_roles():
    return ok([r.to_dict() for r in reference_service.list_roles()])


def list_courses():
    return ok([c.to_dict(include_components=True) for c in reference_service.list_courses()])


def list_staff():
    v = Validator(request.args.to_dict())
    v.string("role", upper=True, max_length=50)
    v.integer("branch_id", min_value=1)
    filters = v.validate()

    scopes = reference_service.list_staff(filters.get("role"), filters.get("branch_id"))
    return ok([{**s.user.to_summary(), "role_code": s.role.role_code, "branch_id": s.branch_id} for s in scopes])
