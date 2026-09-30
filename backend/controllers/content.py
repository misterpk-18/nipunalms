from flask import request, send_file

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated, require_changes
from models.content import CONTENT_STATUSES, CONTENT_TYPES
from services import content as content_service
from services.errors import ValidationError


def _statuses() -> list[str] | None:
    """?status=Submitted,Under Review — one or more content statuses."""
    raw = request.args.get("status")
    if not raw:
        return None
    statuses = [s.strip() for s in raw.split(",") if s.strip()]
    bad = [s for s in statuses if s not in CONTENT_STATUSES]
    if bad:
        raise ValidationError("Invalid filter", {"status": [f"Must be one of: {', '.join(CONTENT_STATUSES)}"]})
    return statuses


def list_items():
    v = Validator(request.args.to_dict())
    for field in ("course_id", "batch_id", "branch_id", "module_id", "topic_id", "owner_user_id"):
        v.integer(field, min_value=1)
    v.choice("content_type", CONTENT_TYPES)
    v.string("q", max_length=100)
    filters = v.validate()
    if statuses := _statuses():
        filters["status"] = statuses

    page, per_page = get_page_params()
    items, meta = content_service.list_items(filters, page, per_page)
    return paginated([i.to_dict() for i in items], meta)


def _payload() -> tuple[dict, object | None]:
    """A JSON body, or a multipart form with an optional `file` part (empty form fields are treated as absent)."""
    if request.mimetype == "multipart/form-data":
        request.max_content_length = content_service.upload_limit_bytes()  # ordinary uploads are limited again per file type
        return {k: v for k, v in request.form.items() if v != ""}, request.files.get("file")
    return json_body(), None


def _item_rules(v: Validator, *, creating: bool) -> None:
    v.string("title", required=creating, max_length=200)
    v.string("description", nullable=True, max_length=5000)
    v.string("language", max_length=2, pattern="en|te", pattern_message="Must be en or te")
    v.integer("course_id", min_value=1)
    v.integer("curriculum_version_id", min_value=1)
    v.integer("module_id", min_value=1)
    v.integer("topic_id", min_value=1)
    v.integer("batch_id", nullable=not creating, min_value=1)
    v.boolean("download_allowed")


def create_item():
    data, upload = _payload()
    v = Validator(data)
    _item_rules(v, creating=True)
    v.choice("content_type", CONTENT_TYPES, required=True)
    v.integer("branch_id", min_value=1)
    v.string("url", nullable=True, max_length=1000)
    v.string("change_summary", nullable=True, max_length=1000)
    item = content_service.create_item(v.validate(), upload)
    return created(item.to_dict(detail=True))


def get_item(content_item_id: int):
    item, reviews = content_service.get_item_detail(content_item_id)
    return ok({**item.to_dict(detail=True), "reviews": [r.to_dict() for r in reviews]})


def update_item(content_item_id: int):
    v = Validator(json_body())
    _item_rules(v, creating=False)
    data = require_changes(v.validate())
    return ok(content_service.update_item(content_item_id, data).to_dict(detail=True))


def add_version(content_item_id: int):
    data, upload = _payload()
    v = Validator(data)
    v.string("url", nullable=True, max_length=1000)
    v.string("change_summary", nullable=True, max_length=1000)
    cleaned = v.validate()
    item = content_service.add_version(content_item_id, upload, cleaned.get("url"), cleaned.get("change_summary"))
    return created(item.to_dict(detail=True))


def submit(content_item_id: int):
    return ok(content_service.submit(content_item_id).to_dict(detail=True))


def review(content_item_id: int):
    v = Validator(json_body())
    v.choice("decision", ("start", "approve", "request_changes", "reject"), required=True)
    v.string("comment", nullable=True, max_length=2000)
    v.boolean("release", default=False)
    data = v.validate()
    item = content_service.review(content_item_id, data["decision"], data.get("comment"), data["release"])
    return ok(item.to_dict(detail=True))


def release(content_item_id: int):
    return ok(content_service.release(content_item_id).to_dict(detail=True))


def retire(content_item_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, max_length=1000)
    return ok(content_service.retire(content_item_id, v.validate()["reason"]).to_dict(detail=True))


def placement_options():
    return ok(content_service.placement_options())


def open_item(content_item_id: int):
    return ok(content_service.open_item(content_item_id))


def get_file(content_item_id: int):
    """The file itself; ?download=true asks for an attachment (refused where the item does not allow downloads)."""
    v = Validator(request.args.to_dict())
    v.boolean("download", default=False)
    path, filename, mime_type, inline = content_service.file_for(content_item_id, v.validate()["download"])
    response = send_file(path, mimetype=mime_type if inline else "application/octet-stream", as_attachment=not inline, download_name=filename)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response
