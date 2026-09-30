from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated, require_changes
from services import admin_users as users_service

STAFF_ROLE_CODES = ("TRAINER", "ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")


def _scope_rules(v: Validator) -> None:
    v.choice("role_code", STAFF_ROLE_CODES, required=True)
    v.integer("branch_id", nullable=True, min_value=1)
    v.datetime("expires_at", nullable=True)


def list_users():
    v = Validator(request.args.to_dict())
    v.string("q", max_length=100)
    v.choice("role_code", STAFF_ROLE_CODES)
    v.integer("branch_id", min_value=1)
    v.boolean("is_active")
    filters = v.validate()

    page, per_page = get_page_params()
    users, meta = users_service.list_users(filters, page, per_page)
    return paginated([u.to_admin_dict() for u in users], meta)


def get_user(user_id: int):
    return ok(users_service.get_user(user_id).to_admin_dict())


def create_user():
    v = Validator(json_body())
    v.string("full_name", required=True, max_length=150)
    v.email("email", required=True)
    v.phone("phone", nullable=True)
    v.list_of("scopes", _scope_rules, required=True, min_items=1)
    user, password = users_service.create_user(v.validate())
    return created({**user.to_admin_dict(), "temporary_password": password})  # shown once


def update_user(user_id: int):
    v = Validator(json_body())
    v.string("full_name", min_length=1, max_length=150)
    v.email("email")
    v.phone("phone", nullable=True)
    return ok(users_service.update_user(user_id, require_changes(v.validate())).to_admin_dict())


def grant_scope(user_id: int):
    v = Validator(json_body())
    _scope_rules(v)
    data = v.validate()
    user = users_service.grant_scope(user_id, data["role_code"], data.get("branch_id"), data.get("expires_at"))
    return created(user.to_admin_dict())


def revoke_scope(user_id: int, scope_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, max_length=500)
    return ok(users_service.revoke_scope(user_id, scope_id, v.validate()["reason"]).to_admin_dict())


def deactivate(user_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, max_length=500)
    return ok(users_service.deactivate(user_id, v.validate()["reason"]).to_admin_dict())


def reactivate(user_id: int):
    v = Validator(json_body())
    v.string("reason", nullable=True, max_length=500)
    return ok(users_service.reactivate(user_id, v.validate().get("reason")).to_admin_dict())


def reset_password(user_id: int):
    user, password = users_service.reset_password(user_id)
    return ok({**user.to_admin_dict(), "temporary_password": password})  # shown once
