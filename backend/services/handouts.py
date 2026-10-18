"""Hand-out of the accounts the role-separation split created (db/118).

Each new account has no password; the Super Admin or Founder issues a one-time activation link (the staff-invite mechanism, only
its hash is stored, so the raw link is shown once) and gives it to the person, then marks the account handed out.
"""
from datetime import datetime, timezone

from config.database import db
from models import SplitAccountHandout
from repositories import handouts as handouts_repo
from repositories.common import paginate
from services import activation, audit
from services.context import current_user
from services.errors import BusinessRule, NotFound


def list_handouts(pending_only: bool, page: int, per_page: int):
    return paginate(handouts_repo.list_stmt(pending_only), page, per_page)


def get_handout(handout_id: int) -> SplitAccountHandout:
    handout = handouts_repo.get(handout_id)
    if handout is None:
        raise NotFound("Hand-out record not found")
    return handout


def issue_link(handout_id: int) -> tuple[SplitAccountHandout, activation.IssuedInvite]:
    """A new one-time link for the account (first issue, or a re-issue when the last one expired); replaces any earlier link."""
    handout = get_handout(handout_id)
    user = handout.user
    if not user.must_change_password:
        raise BusinessRule("This person has already activated the account")
    scopes = [s for s in user.scopes if s.revoked_at is None]
    branch_name = ", ".join(s.branch.branch_name for s in scopes if s.branch_id) or "all branches"
    issued = activation.issue_invite(user, issued_by=current_user().user_id, role_name=handout.role.role_name, branch_name=branch_name)
    handout.invite = issued.invite
    audit.record("SPLIT_ACCOUNT_LINK_ISSUED", "user", user.user_id, new={"handout_id": handout.handout_id, "expires_at": issued.invite.expires_at})
    return handout, issued


def mark_handed_out(handout_id: int) -> SplitAccountHandout:
    handout = get_handout(handout_id)
    if handout.handed_out_at is not None:
        raise BusinessRule("This account is already marked as handed out")
    handout.handed_out_at, handout.handed_out_by = datetime.now(timezone.utc), current_user().user_id
    db.session.flush()
    audit.record("SPLIT_ACCOUNT_HANDED_OUT", "user", handout.user_id, new={"handout_id": handout.handout_id})
    return handout
