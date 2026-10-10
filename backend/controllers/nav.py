from flask import request

from controllers.common import Validator, ok
from services import nav as nav_service
from services import search as search_service

WORKSPACES = ("student", "trainer", "branch", "admin", "founder")


def _args() -> dict:
    v = Validator(request.args.to_dict())
    v.choice("workspace", WORKSPACES, required=True)
    v.integer("branch_id", min_value=1)
    return v.validate()


def nav_counts():
    args = _args()
    return ok(nav_service.nav_counts(args["workspace"], args.get("branch_id")))


def getting_started():
    args = _args()
    return ok(nav_service.getting_started(args["workspace"], args.get("branch_id")))


def search():
    v = Validator(request.args.to_dict())
    v.string("q", max_length=100)
    return ok(search_service.search(v.validate().get("q") or ""))
