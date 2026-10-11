"""Switching AI off (Module 24 §11). The Super Admin and the Founder / CEO can each immediately switch an assistant off for
students or staff, or all AI off, company-wide or (for one audience) at one branch, and each can restore it (UX phase U17: the
Super Admin may now switch all AI off and restore it too). Each control records the scope, reason, actor, time and remediation;
restoring it records who restored it and which checks passed. While a control is active, Ask Nipuna shows Disabled to the
people it covers. `status()` is the ON / OFF picture per audience that the AI controls page shows."""
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


def _may_control() -> None:
    if not current_user().has_role("FOUNDER_CEO", "SUPER_ADMIN"):
        raise Forbidden("Only the Super Admin or Founder / CEO can switch AI off or restore it")


def disable(audience: str, branch_id: int | None, reason: str, remediation: str | None) -> AiFeatureControl:
    _may_control()
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
    _may_control()
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


AUDIENCES = (("Student", "Student assistant"), ("Staff", "Staff assistant"))


def status() -> dict:
    """ON / OFF per audience for the whole company, the branch-level switches, and a company-wide "all AI" switch.

    An audience is Off company-wide when a control for it (or for All) with no branch is active. `via_all` says it is off only
    because all AI is off. Branch switches are listed separately: they leave the rest of the company on.
    """
    active = [c for c in db.session.execute(select(AiFeatureControl).where(AiFeatureControl.restored_at.is_(None))
                                            .order_by(AiFeatureControl.disabled_at)).scalars().unique()]
    company_all = next((c for c in active if c.audience == "All" and c.branch_id is None), None)
    audiences = []
    for code, label in AUDIENCES:
        own = next((c for c in active if c.audience == code and c.branch_id is None), None)
        control = own or company_all
        audiences.append({"audience": code, "label": label, "state": "Off" if control else "On",
                          "control": control.to_dict() if control else None, "via_all": control is not None and own is None})
    return {
        "audiences": audiences,
        "all": {"state": "Off" if company_all else "On", "control": company_all.to_dict() if company_all else None},
        "branches": [c.to_dict() for c in active if c.branch_id is not None],
        "can_switch": current_user().has_role("FOUNDER_CEO", "SUPER_ADMIN"),
    }
