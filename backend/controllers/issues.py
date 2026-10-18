from flask import request

from controllers.common import Validator, get_page_params, ok, paginated
from services import issues as issues_service


def list_issues():
    v = Validator(request.args.to_dict())
    v.string("type", max_length=20)
    v.string("age", max_length=20)
    v.string("owner", max_length=20)
    v.integer("branch_id", min_value=1)
    page, per_page = get_page_params()
    rows, meta = issues_service.list_issues(v.validate(), page, per_page)
    return paginated(rows, meta)


def get_issue(source: str, source_id: int):
    return ok(issues_service.get_issue(source, source_id))
