"""Content library: authoring, versions, academic review, release and retirement, and what students may open.

Lifecycle of a version: Draft -> Submitted -> Under Review -> Approved -> Released, or Changes Requested / Rejected;
a newer Released version retires the previous one, and an item can be Retired as a whole. The item's `status` follows its
latest version, but students keep the last Released version until a newer one is released (Module 18 §9).

Who may do what:
  Trainer               add content for batches they teach, edit their drafts, submit
  Academic Coordinator  review, release and retire content at their branch (never their own upload)
  Branch Manager        sees the branch's content
  Super Admin           all branches
  Student               sees Released items of their own enrolments, until the access window closes
"""
from datetime import datetime, timezone
from urllib.parse import urlparse

from werkzeug.datastructures import FileStorage

from config.database import db
from models import ContentItem, ContentReview, ContentVersion, Enrolment
from models.content import LINK_CONTENT_TYPES
from repositories import batches as batches_repo
from repositories import catalog as catalog_repo
from repositories import content as content_repo
from repositories import users as users_repo
from repositories.common import paginate
from services import audit, content_files, scope, student_library
from services.context import current_user
from services.errors import BusinessRule, Forbidden, NotFound, ValidationError
from services.notifications import notify

PLACEMENT_KEYS = ("topic_id", "module_id", "curriculum_version_id", "batch_id")
REVIEWABLE = ("Submitted", "Under Review")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- who may see / manage

def _is_reviewer(item: ContentItem) -> bool:
    """Academic Coordinator of the item's branch, or Super Admin."""
    user = current_user()
    return user.has_role("SUPER_ADMIN") or user.has_role("ACADEMIC_COORDINATOR", branch_id=item.branch_id)


def _staff_can_view(item: ContentItem) -> bool:
    user = current_user()
    branch_ids = scope.visible_branch_ids(user)
    return (branch_ids is None or item.branch_id in branch_ids or item.owner_user_id == user.user_id
            or (item.batch_id is not None and item.batch_id in scope.trainer_batch_ids(user)))


def _get_staff_item(content_item_id: int) -> ContentItem:
    item = content_repo.get_item(content_item_id)
    if item is None or not _staff_can_view(item):
        raise NotFound("Content item not found")
    return item


def _assert_can_manage(item: ContentItem) -> None:
    """Author (while the item is theirs to change) or a reviewer of the branch."""
    user = current_user()
    if _is_reviewer(item):
        return
    if item.owner_user_id == user.user_id:
        return
    raise Forbidden("You can only change content you added")


def _assert_open(item: ContentItem) -> None:
    if item.retired_at is not None:
        raise BusinessRule("This content item is retired")


# ---------------------------------------------------------------- audience (which enrolments are entitled)

def item_matches_enrolment(item: ContentItem, enrolment: Enrolment, batch_id: int | None) -> bool:
    """The audience rule: same branch and course, the item's batch (if any) is the enrolment's batch, and the item's
    curriculum version (if any) is the enrolment's version or one of its combo tracks' versions."""
    if item.branch_id != enrolment.service_branch_id or item.course_id != enrolment.course_id:
        return False
    if item.batch_id is not None and item.batch_id != batch_id:
        return False
    if item.curriculum_version_id is None:
        return True
    return item.curriculum_version_id in {enrolment.curriculum_version_id, *(t.curriculum_version_id for t in enrolment.tracks)}


def audience(item: ContentItem) -> list[Enrolment]:
    """Enrolments entitled to this item (whether or not it is released yet)."""
    enrolments = content_repo.audience_enrolments(item.branch_id, item.course_id)
    allocations = batches_repo.active_allocations([e.enrolment_id for e in enrolments])
    return [e for e in enrolments
            if item_matches_enrolment(item, e, allocations[e.enrolment_id].batch_id if e.enrolment_id in allocations else None)]


def _audience_user_ids(item: ContentItem) -> list[int]:
    user_ids = []
    for enrolment in audience(item):
        user = users_repo.get_by_student_id(enrolment.student_id)
        if user is not None and user.user_id not in user_ids:
            user_ids.append(user.user_id)
    return user_ids


# ---------------------------------------------------------------- placement

def _resolve_placement(data: dict, current: ContentItem | None = None) -> dict:
    """course / curriculum version / module / topic from whichever of topic, module, version or course was given."""
    topic = module = version = None
    if data.get("topic_id"):
        topic = content_repo.get_topic(data["topic_id"])
        if topic is None:
            raise ValidationError("Invalid placement", {"topic_id": ["Unknown topic"]})
        module, version = topic.module, topic.module.version
    elif data.get("module_id"):
        module = content_repo.get_module(data["module_id"])
        if module is None:
            raise ValidationError("Invalid placement", {"module_id": ["Unknown module"]})
        version = module.version
    elif data.get("curriculum_version_id"):
        version = content_repo.get_version(data["curriculum_version_id"])
        if version is None:
            raise ValidationError("Invalid placement", {"curriculum_version_id": ["Unknown curriculum version"]})

    if version is not None:
        course_id = version.course_id
    elif data.get("course_id"):
        if catalog_repo.get_course(data["course_id"]) is None:
            raise ValidationError("Invalid placement", {"course_id": ["Unknown course"]})
        course_id = data["course_id"]
    elif current is not None:
        course_id = current.course_id
    else:
        raise ValidationError("Choose where this belongs", {"topic_id": ["Choose a course, curriculum version, module or topic"]})
    if data.get("course_id") and data["course_id"] != course_id:
        raise ValidationError("Invalid placement", {"course_id": ["The topic or version belongs to a different course"]})
    return {
        "course_id": course_id,
        "curriculum_version_id": version.curriculum_version_id if version else None,
        "module_id": module.module_id if module else None,
        "topic_id": topic.topic_id if topic else None,
    }


def _authoring_branch(course_id: int, batch, requested_branch_id: int | None) -> int:
    """The branch a new item belongs to, from the batch or from where the author works; never from a free choice."""
    user = current_user()
    if batch is not None:
        if batch.course_id != course_id:
            raise ValidationError("Invalid placement", {"batch_id": ["The batch is for a different course"]})
        branch_ids = scope.visible_branch_ids(user)
        if not (branch_ids is None or batch.branch_id in branch_ids or batch.batch_id in scope.trainer_batch_ids(user)):
            raise Forbidden("You can only add content for batches you teach or manage")
        return batch.branch_id

    branch_ids = scope.visible_branch_ids(user)
    trainer_branches = {b.branch_id for b in (batches_repo.get_batch(i) for i in scope.trainer_batch_ids(user))
                        if b is not None and b.course_id == course_id}
    if branch_ids is None:  # Super Admin / Founder: any branch, stated explicitly
        if requested_branch_id is None:
            raise ValidationError("Choose a branch", {"branch_id": ["Required"]})
        return requested_branch_id
    candidates = branch_ids | trainer_branches
    if requested_branch_id is not None:
        if requested_branch_id not in candidates:
            raise Forbidden("You can only add content for your own branch and courses")
        return requested_branch_id
    if len(candidates) == 1:
        return next(iter(candidates))
    if not candidates:
        raise Forbidden("You are not assigned to a batch of this course")
    raise ValidationError("Choose a branch", {"branch_id": ["Required"]})


def _clean_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValidationError("Invalid link", {"url": ["Enter a full http(s) address"]})
    return url


def _source_of(content_type: str, upload: FileStorage | None, url: str | None) -> dict:
    """The version columns for a file upload or a link, checked against the content type."""
    if content_type in LINK_CONTENT_TYPES:
        if upload is not None:
            raise ValidationError("A link has no file", {"file": ["Links are added by address, not by upload"]})
        if not url:
            raise ValidationError("Add the link", {"url": ["Required"]})
        return {"storage_kind": "Link", "url": _clean_url(url)}
    if url:
        raise ValidationError("A file needs no link", {"url": ["Only link types take an address"]})
    if upload is None or not upload.filename:
        raise ValidationError("Upload the file", {"file": ["Required"]})
    stored = content_files.save_content_file(upload)
    return {"storage_kind": "File", "file_path": stored.file_path, "original_filename": stored.original_filename,
            "mime_type": stored.mime_type, "file_size_bytes": stored.file_size_bytes}


# ---------------------------------------------------------------- authoring

def create_item(data: dict, upload: FileStorage | None) -> ContentItem:
    """A new item with its first version (Draft)."""
    user = current_user()
    placement = _resolve_placement(data)
    batch = None
    if data.get("batch_id"):
        batch = batches_repo.get_batch(data["batch_id"])
        if batch is None:
            raise ValidationError("Invalid placement", {"batch_id": ["Unknown batch"]})
    branch_id = _authoring_branch(placement["course_id"], batch, data.get("branch_id"))
    source = _source_of(data["content_type"], upload, data.get("url"))

    try:
        item = ContentItem(
            title=data["title"], description=data.get("description"), content_type=data["content_type"],
            language=data.get("language", "en"), branch_id=branch_id, batch_id=batch.batch_id if batch else None,
            download_allowed=data.get("download_allowed", data["content_type"] not in LINK_CONTENT_TYPES),
            owner_user_id=user.user_id, **placement,
        )
        item.versions.append(ContentVersion(version_no=1, uploaded_by=user.user_id, change_summary=data.get("change_summary"), **source))
        db.session.add(item)
        db.session.flush()
    except Exception:
        if source.get("file_path"):
            content_files.delete_file(source["file_path"])
        raise
    db.session.refresh(item)
    audit.record("CONTENT_CREATED", "content_item", item.item_code, new={"title": item.title, "content_type": item.content_type,
                                                                          "version": 1}, branch_id=item.branch_id)
    return item


def update_item(content_item_id: int, data: dict) -> ContentItem:
    """Edit title, description, language, download policy and placement. Authors while the version is still theirs to
    change (Draft / Changes Requested); reviewers any time, audited with old and new values."""
    item = _get_staff_item(content_item_id)
    _assert_can_manage(item)
    _assert_open(item)
    reviewer = _is_reviewer(item)
    if not reviewer and item.latest_version.status not in ("Draft", "Changes Requested"):
        raise BusinessRule(f"The latest version is {item.latest_version.status}; it can only be changed by the reviewer")

    old = {key: getattr(item, key) for key in ("title", "description", "language", "download_allowed", "curriculum_version_id",
                                               "module_id", "topic_id", "batch_id")}
    for key in ("title", "description", "language", "download_allowed"):
        if key in data:
            setattr(item, key, data[key])
    if any(key in data for key in PLACEMENT_KEYS):
        placement_input = {key: data[key] for key in ("topic_id", "module_id", "curriculum_version_id") if key in data}
        placement = _resolve_placement(placement_input, current=item) if placement_input else {
            "course_id": item.course_id, "curriculum_version_id": item.curriculum_version_id,
            "module_id": item.module_id, "topic_id": item.topic_id}
        if placement["course_id"] != item.course_id:
            raise ValidationError("Invalid placement", {"topic_id": ["Content cannot move to another course; add a new item"]})
        for key, value in placement.items():
            setattr(item, key, value)
        if "batch_id" in data:
            batch = batches_repo.get_batch(data["batch_id"]) if data["batch_id"] else None
            if data["batch_id"] and batch is None:
                raise ValidationError("Invalid placement", {"batch_id": ["Unknown batch"]})
            if batch is not None and batch.branch_id != item.branch_id:
                raise ValidationError("Invalid placement", {"batch_id": ["The batch is at a different branch"]})
            item.batch_id = batch.batch_id if batch else None
    db.session.flush()
    db.session.refresh(item)
    new = {key: getattr(item, key) for key in old}
    if new != old:
        audit.record("CONTENT_UPDATED", "content_item", item.item_code, old=old, new=new, branch_id=item.branch_id)
    return item


def add_version(content_item_id: int, upload: FileStorage | None, url: str | None, change_summary: str | None) -> ContentItem:
    """Upload a new version (v2, v3 ...). Earlier versions are kept; students keep the released one until this is released."""
    item = _get_staff_item(content_item_id)
    _assert_can_manage(item)
    _assert_open(item)
    latest = item.latest_version
    if latest.status in REVIEWABLE:
        raise BusinessRule(f"Version {latest.version_no} is waiting for review; wait for the decision before uploading another")
    if (latest.storage_kind == "Link") != (item.content_type in LINK_CONTENT_TYPES):
        raise BusinessRule("The item type and its source do not match")
    source = _source_of(item.content_type, upload, url)

    try:
        for version in item.versions:  # an unfinished earlier version is superseded, not deleted
            if version.status in ("Draft", "Changes Requested", "Approved"):
                version.status = "Retired"
        item.versions.append(ContentVersion(version_no=content_repo.next_version_no(item.content_item_id),
                                            uploaded_by=current_user().user_id, change_summary=change_summary, **source))
        item.status = "Draft"
        db.session.flush()
    except Exception:
        if source.get("file_path"):
            content_files.delete_file(source["file_path"])
        raise
    audit.record("CONTENT_VERSION_ADDED", "content_item", item.item_code,
                 new={"version": item.latest_version.version_no, "change_summary": change_summary}, branch_id=item.branch_id)
    return item


def submit(content_item_id: int) -> ContentItem:
    """Send the latest version to the Academic Coordinator for review."""
    item = _get_staff_item(content_item_id)
    _assert_can_manage(item)
    _assert_open(item)
    version = item.latest_version
    if version.status not in ("Draft", "Changes Requested"):
        raise BusinessRule(f"Version {version.version_no} is {version.status} and cannot be submitted")
    version.status = "Submitted"
    version.submitted_at = _now()
    item.status = "Submitted"
    _log_review(item, version, "Submitted")
    audit.record("CONTENT_SUBMITTED", "content_item", item.item_code, new={"version": version.version_no}, branch_id=item.branch_id)
    notify(category="Content", title=f"Content submitted for review: {item.title}",
           body=f"{current_user().full_name} submitted version {version.version_no} of {item.item_code}.",
           link="/academic/content-review", role_code="ACADEMIC_COORDINATOR", branch_id=item.branch_id,
           event_key=f"content-submitted-{version.content_version_id}", action_required=True)
    return item


def _log_review(item: ContentItem, version: ContentVersion, action: str, comment: str | None = None) -> None:
    db.session.add(ContentReview(content_item_id=item.content_item_id, content_version_id=version.content_version_id,
                                 action=action, actor_user_id=current_user().user_id, comment=comment))
    db.session.flush()


# ---------------------------------------------------------------- academic review

def review(content_item_id: int, decision: str, comment: str | None, release_now: bool = False) -> ContentItem:
    """start / approve / request_changes / reject the version under review; a reviewer never reviews their own upload."""
    item = _get_staff_item(content_item_id)
    if not _is_reviewer(item):
        raise Forbidden("Only the Academic Coordinator of this branch reviews content")
    _assert_open(item)
    version = item.latest_version
    if version.status not in REVIEWABLE:
        raise BusinessRule(f"Version {version.version_no} is {version.status}; only submitted content can be reviewed")
    if version.uploaded_by == current_user().user_id:
        raise BusinessRule("You cannot review content you uploaded; ask another reviewer")
    if decision in ("request_changes", "reject") and not (comment or "").strip():
        raise ValidationError("Say what needs to change", {"comment": ["Required for this decision"]})

    outcome = {"start": "Under Review", "approve": "Approved", "request_changes": "Changes Requested", "reject": "Rejected"}[decision]
    if decision == "start" and version.status == "Under Review":
        raise BusinessRule("The review has already started")
    version.status = outcome
    item.status = outcome
    action = {"Under Review": "Review Started"}.get(outcome, outcome)
    _log_review(item, version, action, comment)
    audit.record("CONTENT_REVIEWED", "content_item", item.item_code, old={"status": "Submitted"},
                 new={"status": outcome, "version": version.version_no}, reason=comment, branch_id=item.branch_id)

    if decision != "start":
        owner = version.uploaded_by
        notify(category="Content", title=f"{item.title}: {outcome.lower()}",
               body=comment or f"Version {version.version_no} of {item.item_code} was approved.", link="/trainer/content",
               recipient_user_ids=[owner], branch_id=item.branch_id, event_key=f"content-reviewed-{version.content_version_id}",
               action_required=decision in ("request_changes",))
    if decision == "approve" and release_now:
        release(content_item_id)
    return item


def release(content_item_id: int) -> ContentItem:
    """Release the approved version to its audience. The previously released version is retired (and kept)."""
    item = _get_staff_item(content_item_id)
    if not _is_reviewer(item):
        raise Forbidden("Only the Academic Coordinator of this branch releases content")
    _assert_open(item)
    version = item.latest_version
    if version.status != "Approved":
        raise BusinessRule(f"Version {version.version_no} is {version.status}; only approved content can be released")
    previous = item.released_version
    if previous is not None:
        previous.status = "Retired"
    version.status = "Released"
    version.released_at = _now()
    version.released_by = current_user().user_id
    item.status = "Released"
    _log_review(item, version, "Released")
    audit.record("CONTENT_RELEASED", "content_item", item.item_code,
                 old={"released_version": previous.version_no if previous else None},
                 new={"released_version": version.version_no, "batch_id": item.batch_id, "topic_id": item.topic_id},
                 branch_id=item.branch_id)
    notify(category="Content", title=f"New material: {item.title}",
           body=("Updated" if previous else "Added") + f" in {item.course.title}" + (f" · {item.topic.title}" if item.topic else ""),
           link="/resources", recipient_user_ids=_audience_user_ids(item), branch_id=item.branch_id,
           event_key=f"content-released-{version.content_version_id}")
    return item


def retire(content_item_id: int, reason: str) -> ContentItem:
    """Withdraw the item from students. Files and versions are kept (no deletion)."""
    item = _get_staff_item(content_item_id)
    if not _is_reviewer(item):
        raise Forbidden("Only the Academic Coordinator of this branch retires content")
    _assert_open(item)
    was_released = item.released_version is not None
    old_status = item.status
    item.status = "Retired"
    item.retired_at = _now()
    item.retired_by = current_user().user_id
    item.retire_reason = reason
    _log_review(item, item.latest_version, "Retired", reason)
    audit.record("CONTENT_RETIRED", "content_item", item.item_code, old={"status": old_status}, new={"status": "Retired"},
                 reason=reason, branch_id=item.branch_id)
    if was_released:
        notify(category="Content", title=f"Material withdrawn: {item.title}", body=reason, link="/resources",
               recipient_user_ids=_audience_user_ids(item), branch_id=item.branch_id, event_key=f"content-retired-{item.content_item_id}")
    return item


# ---------------------------------------------------------------- staff reads

def list_items(filters: dict, page: int, per_page: int) -> tuple[list[ContentItem], dict]:
    user = current_user()
    stmt = content_repo.list_stmt(filters, scope.visible_branch_ids(user), user.user_id, scope.trainer_batch_ids(user))
    return paginate(stmt, page, per_page)


def get_item_detail(content_item_id: int) -> tuple[ContentItem, list[ContentReview]]:
    item = _get_staff_item(content_item_id)
    return item, content_repo.reviews_of(item.content_item_id)


def placement_options() -> list[dict]:
    """What an author can attach content to: each batch they may manage, with the curriculum versions, modules and topics."""
    user = current_user()
    branch_ids = scope.visible_branch_ids(user)
    batches = content_repo.batches_for_authoring(branch_ids, scope.trainer_batch_ids(user))
    if not user.has_role("TRAINER", "ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO"):
        return []
    options = []
    for batch in batches:
        versions = content_repo.versions_with_modules(batch.course_id, batch.curriculum_version_id)
        tracks = content_repo.track_labels({v.curriculum_version_id for v in versions})
        options.append({
            "batch": batch.to_summary(),
            "course": batch.course.to_summary(),
            "branch": batch.branch.to_summary(),
            "versions": [{
                "curriculum_version_id": v.curriculum_version_id,
                "version_label": v.version_label,
                "track_name": tracks.get(v.curriculum_version_id, {}).get("track_name"),
                "modules": [{"module_id": m.module_id, "title": m.title,
                             "topics": [{"topic_id": t.topic_id, "title": t.title} for t in m.topics]} for m in v.modules],
            } for v in versions],
        })
    return options


# ---------------------------------------------------------------- student reads

def _best_enrolment(item: ContentItem, ctx: student_library.StudentContext) -> Enrolment | None:
    """The student's enrolment that entitles them to the item; when several do, the one with the most usable access."""
    matching = [e for e in ctx.enrolments if item_matches_enrolment(item, e, ctx.batch_by_enrolment[e.enrolment_id])]
    rank = {"Available": 0, "Pending": 1, "Expired": 2}
    matching.sort(key=lambda e: rank[ctx.windows[e.enrolment_id].state("Material", ctx.today)])
    return matching[0] if matching else None


def _student_entry(item: ContentItem, enrolment: Enrolment, ctx: student_library.StudentContext, tracks: dict) -> dict:
    version = item.released_version
    window = ctx.windows[enrolment.enrolment_id]
    return {
        **item.to_summary(),
        "description": item.description,
        "language": item.language,
        "course": item.course.to_summary(),
        "track": tracks.get(item.curriculum_version_id),
        "module": {"module_id": item.module.module_id, "title": item.module.title} if item.module else None,
        "topic": {"topic_id": item.topic.topic_id, "title": item.topic.title} if item.topic else None,
        "storage_kind": version.storage_kind,
        "original_filename": version.original_filename,
        "version_no": version.version_no,
        "file_size_bytes": version.file_size_bytes,
        "download_allowed": item.download_allowed and version.storage_kind == "File",
        "released_at": version.released_at,
        "enrolment": enrolment.to_summary(),
        "access": window.describe("Material", ctx.today),
    }


def student_resources(filters: dict) -> list[dict]:
    """Released items of the student's own enrolments, with the access window of the enrolment that entitles them."""
    ctx = student_library.student_context()
    candidates = content_repo.released_candidates({e.service_branch_id for e in ctx.enrolments},
                                                  {e.course_id for e in ctx.enrolments}, filters)
    entries = [(item, enrolment) for item in candidates if (enrolment := _best_enrolment(item, ctx)) is not None]
    tracks = content_repo.track_labels({item.curriculum_version_id for item, _ in entries})
    return [_student_entry(item, enrolment, ctx, tracks) for item, enrolment in entries]


def _student_item(content_item_id: int) -> tuple[ContentItem, Enrolment, student_library.StudentContext]:
    """A released item the student is entitled to; anything else is a 404. Expired access is a business rule error."""
    ctx = student_library.student_context()
    item = content_repo.get_item(content_item_id)
    if item is None or item.released_version is None:
        raise NotFound("Content item not found")
    enrolment = _best_enrolment(item, ctx)
    if enrolment is None:
        raise NotFound("Content item not found")
    window = ctx.windows[enrolment.enrolment_id]
    if window.state("Material", ctx.today) == "Expired":
        raise BusinessRule(f"Your access to materials for {enrolment.course.title} ended on {window.expiry['Material']:%d %b %Y}. "
                           "You can request an extension from the Resources screen.")
    return item, enrolment, ctx


def open_item(content_item_id: int) -> dict:
    """Open a resource: records the view for a student and says where to get it (a link's address, or the file)."""
    user = current_user()
    if user.student_id is not None:
        item, enrolment, _ = _student_item(content_item_id)
        version = item.released_version
        content_repo.record_activity(user.student_id, enrolment.enrolment_id, "resource_view",
                                     {"content_item_id": item.content_item_id, "item_code": item.item_code,
                                      "version_no": version.version_no})
    else:
        item = _get_staff_item(content_item_id)
        version = item.latest_version
    return {
        **item.to_summary(),
        "version_no": version.version_no,
        "storage_kind": version.storage_kind,
        "url": version.url,
        "original_filename": version.original_filename,
        "download_allowed": item.download_allowed or user.student_id is None,
        "inline": version.storage_kind == "File" and content_files.is_inline(version.original_filename),
    }


def file_for(content_item_id: int, download: bool) -> tuple[str, str | None, str | None, bool]:
    """(path, filename, mime type, show in browser) of the file to serve. Entitlement, expiry and the download policy are
    decided here, at retrieval. Staff preview the latest version; students get the released one."""
    user = current_user()
    if user.student_id is not None:
        item, _, _ = _student_item(content_item_id)
        if download and not item.download_allowed:
            raise Forbidden("Downloading is not permitted for this resource; open it in the browser instead")
        version = item.released_version
    else:
        item = _get_staff_item(content_item_id)
        version = item.latest_version
    if version.storage_kind != "File":
        raise BusinessRule("This item is a link, not a file")
    path = content_files.resolve(version.file_path)
    return str(path), version.original_filename, version.mime_type, content_files.is_inline(version.original_filename) and not download


def upload_limit_bytes() -> int:
    """Request size to allow for content uploads (the dataset limit, plus a little for the form fields)."""
    return content_files.max_upload_bytes() + 1024 * 1024
