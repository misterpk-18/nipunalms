"""Switching AI off (Module 24 §11). The Super Admin can immediately switch an assistant off for students or staff,
company-wide or at one branch; the Founder / CEO can also switch all AI off company-wide. Each control records the scope,
reason, actor, time and remediation; restoring it records who restored it and which checks passed. While a control is
active, Ask Nipuna shows Disabled to the people it covers."""
from datetime import datetime, timezone

from sqlalchemy import or_, select

from config.database import db
from models import AiFeatureControl
from repositories.common import paginate
from services import audit, scope
from services.context import current_user
from services.errors import BusinessRule, Forbidden, NotFound, ValidationError


def active_control(audience: str, branch_id: int | None) -> AiFeatureControl | None:
    """The control switching this audience off at this branch (or company-wide), if any."""
    stmt = select(AiFeatureControl).where(
        AiFeatureControl.restored_at.is_(None),
        AiFeatureControl.audience.in_(("All", audience)),
        or_(AiFeatureControl.branch_id.is_(None), AiFeatureControl.branch_id == branch_id) if branch_id is not None
        else AiFeatureControl.branch_id.is_(None),
    ).order_by(AiFeatureControl.disabled_at).limit(1)
    return db.session.execute(stmt).scalars().first()


def _may_control(audience: str) -> None:
    user = current_user()
    if audience == "All" and not user.has_role("FOUNDER_CEO"):
        raise Forbidden("Only the Founder / CEO can switch all AI off company-wide; the Super Admin switches one assistant off")
    if not user.has_role("FOUNDER_CEO", "SUPER_ADMIN"):
        raise Forbidden("Only the Super Admin or Founder / CEO can switch AI off")


def disable(audience: str, branch_id: int | None, reason: str, remediation: str | None) -> AiFeatureControl:
    _may_control(audience)
    if audience == "All" and branch_id is not None:
        raise ValidationError("Invalid request data", {"branch_id": ["Switching all AI off is company-wide"]})
    if branch_id is not None:
        scope.require_branch(branch_id)
    if active_control(audience, branch_id) is not None:
        raise BusinessRule("AI is already switched off for this audience and scope")
    control = AiFeatureControl(audience=audience, branch_id=branch_id, reason=reason, remediation=remediation,
                               disabled_by=current_user().user_id)
    db.session.add(control)
    db.session.flush()
    audit.record("AI_DISABLED", "ai_feature_control", control.control_id, new={"audience": audience, "branch_id": branch_id},
                 reason=reason, branch_id=branch_id)
    return control


def restore(control_id: int, note: str) -> AiFeatureControl:
    """Restore only after the checks pass: the note records which."""
    control = db.session.get(AiFeatureControl, control_id)
    if control is None:
        raise NotFound("AI control not found")
    _may_control(control.audience)
    if control.restored_at is not None:
        raise BusinessRule("This control was already restored")
    control.restored_by, control.restored_at, control.restoration_note = current_user().user_id, datetime.now(timezone.utc), note
    db.session.flush()
    audit.record("AI_RESTORED", "ai_feature_control", control.control_id, old={"active": True}, new={"active": False},
                 reason=note, branch_id=control.branch_id)
    return control


def list_controls(active_only: bool, page: int, per_page: int):
    stmt = select(AiFeatureControl).order_by(AiFeatureControl.disabled_at.desc(), AiFeatureControl.control_id.desc())
    if active_only:
        stmt = stmt.where(AiFeatureControl.restored_at.is_(None))
    return paginate(stmt, page, per_page)
