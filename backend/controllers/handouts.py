from datetime import datetime, timezone

from flask import request

from controllers.common import Validator, created, get_page_params, ok, paginated
from services import handouts as handouts_service


def handout_dict(h) -> dict:
    """One hand-out row. The raw link is never here; it comes back once from issue_link."""
    now = datetime.now(timezone.utc)
    live = [s for s in h.user.scopes if s.revoked_at is None]
    return {
        "handout_id": h.handout_id,
        "user_id": h.user_id,
        "full_name": h.user.full_name,
        "email": h.user.email,
        "split_from_email": h.split_from.email,
        "role_code": h.role.role_code,
        "role_name": h.role.role_name,
        "branches": [{"branch_id": s.branch_id, "branch_name": s.branch.branch_name} for s in live if s.branch_id],
        "activated": not h.user.must_change_password,
        "link_status": h.invite.status(now) if h.invite else "none",  # none / valid / expired / used / revoked
        "link_expires_at": h.invite.expires_at if h.invite else None,
        "created_at": h.created_at,
        "handed_out_at": h.handed_out_at,
        "handed_out_by": h.handed_out_by_user.full_name if h.handed_out_by_user else None,
    }


def list_handouts():
    v = Validator(request.args.to_dict())
    v.boolean("pending_only")
    filters = v.validate()
    page, per_page = get_page_params()
    rows, meta = handouts_service.list_handouts(bool(filters.get("pending_only")), page, per_page)
    return paginated([handout_dict(h) for h in rows], meta)


def issue_link(handout_id: int):
    handout, issued = handouts_service.issue_link(handout_id)
    return created({**handout_dict(handout), "invite_path": f"/activate?token={issued.token}"})  # shown once


def mark_handed_out(handout_id: int):
    return ok(handout_dict(handouts_service.mark_handed_out(handout_id)))
