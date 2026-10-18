from flask import request

from controllers.common import Validator, ok
from services import nav as nav_service
from services import search as search_service

WORKSPACES = ("student", "trainer", "branch", "admin", "founder")


def _args() -> dict:
    """`workspace` and `branch_id` are accepted (the frontend still sends them until R4) but the session's role decides."""
    v = Validator(request.args.to_dict())
    v.choice("workspace", WORKSPACES)
    v.integer("branch_id", min_value=1)
    return v.validate()


def nav_counts():
    _args()
    return ok(nav_service.nav_counts())


def getting_started():
    _args()
    return ok(nav_service.getting_started())


def search():
    v = Validator(request.args.to_dict())
    v.string("q", max_length=100)
    return ok(search_service.search(v.validate().get("q") or ""))
