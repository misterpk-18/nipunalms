"""The Audit log in plain sentences (UX phase U17): one sentence per entry, a link to the person or record it is about, and the
preset filters (Accounts, Roles, Integrations).

`SENTENCES` maps an action to a template. `{actor}` is who did it, `{target}` what it was done to (a name where the record can be
found, else its type and id), `{reason}` the reason given, and `{new.key}` / `{old.key}` a value from the snapshot. A missing value
leaves nothing behind. An action with no template still reads as a sentence ("Certificate issued by Asha Rao"), so a new action
shows up readably before anyone adds a line for it.
"""
import re

from sqlalchemy import select

from config.database import db
from models import AuditLog, Batch, ClassSession, CrmEvent, Course, Integration, SecurityControl, Student, User
from models.calendar import CalendarClosure
from models.ask_nipuna import AiFeatureControl

SENTENCES: dict[str, str] = {
    # accounts and sign-in
    "USER_CREATED": "{actor} added the staff account of {target}",
    "USER_UPDATED": "{actor} changed the details of {target}",
    "USER_DEACTIVATED": "{actor} deactivated {target}",
    "USER_REACTIVATED": "{actor} reactivated {target}",
    "USER_UNLOCKED": "{actor} unlocked {target}",
    "PASSWORD_RESET": "{actor} reset the password of {target}",
    "PASSWORD_CHANGED": "{actor} changed their password",
    "PASSWORD_RESET_CODE_REQUESTED": "{target} asked for a password reset code",
    "PASSWORD_RESET_WITH_CODE": "{target} set a new password with a reset code",
    "STAFF_INVITE_SENT": "{actor} sent {target} an invite link",
    "STAFF_INVITE_ACCEPTED": "{target} accepted their invite and chose a password",
    "ACCOUNT_ACTIVATED": "{target} activated their account",
    "ACTIVATION_ISSUED": "{actor} sent {target} an activation link",
    "ACTIVATION_REISSUED": "{actor} sent {target} a new activation link",
    "STUDENT_SUSPENDED": "{actor} suspended the account of {target}",
    "STUDENT_REACTIVATED": "{actor} reactivated the account of {target}",
    "STUDENT_SESSIONS_REVOKED": "{actor} signed {target} out everywhere",
    "STUDENT_EMAIL_CHANGED": "{actor} changed the email of {target}",
    "EMAIL_CHANGE_CODE_REQUESTED": "{actor} asked for a code to change their email",
    "OTHER_SESSIONS_REVOKED": "{actor} signed out their other sessions",
    "SESSION_REVOKED": "{actor} ended a sign-in session of {target}",
    "LOGIN": "{actor} signed in",
    "LOGOUT": "{actor} signed out",
    "SCOPE_GRANTED": "{actor} gave {target} the role {new.role_code}",
    "SCOPE_REVOKED": "{actor} took a role away from {target}",
    # setup, integrations and AI
    "INTEGRATION_UPDATED": "{actor} updated the setup of {target}",
    "SECURITY_CONTROL_UPDATED": "{actor} updated the setup of {target}",
    "AI_DISABLED": "{actor} switched the AI off ({new.audience})",
    "AI_RESTORED": "{actor} switched the AI back on",
    "AI_BUDGET_APPROVED": "{actor} set the monthly AI budget",
    "CRM_EVENT_RETRIED": "{actor} retried the CRM update {target}",
    "BRANCH_PAYMENT_INSTRUCTIONS_CHANGED": "{actor} changed the payment instructions of {target}",
    # calendar
    "CALENDAR_CLOSURE_APPROVED": "{actor} approved the closure {target}",
    "CALENDAR_CLOSURE_PROPOSED": "{actor} proposed the closure {target}",
    "CALENDAR_CLOSURE_REJECTED": "{actor} rejected the closure {target}",
    "CALENDAR_CLOSURE_UPDATED": "{actor} changed the closure {target}",
    "CALENDAR_CLOSURE_CANCELLED": "{actor} cancelled the closure {target}",
    # issues
    "EXCEPTION_STEP_LOGGED": "{actor} added a note to an issue: {new.title}",
    # batches and classes
    "BATCH_CREATED": "{actor} created the batch {target}",
    "BATCH_UPDATED": "{actor} changed the batch {target}",
    "BATCH_STATE": "{actor} moved the batch {target} to {new.state}",
    "BATCH_READINESS": "{actor} checked whether the batch {target} is ready",
    "BATCH_TRAINER_ASSIGNED": "{actor} gave the batch {target} a trainer",
    "BATCH_TRAINER_ENDED": "{actor} ended a trainer's work on the batch {target}",
    "BATCH_TRAINER_ROLE": "{actor} changed a trainer's role on the batch {target}",
    "BATCH_HANDOVER": "{actor} handed the batch {target} to another trainer",
    "BATCH_ALLOCATED": "{actor} put a student in a batch",
    "BATCH_DEALLOCATED": "{actor} took a student out of a batch",
    "BATCH_TRANSFERRED": "{actor} moved a student to another batch",
    "BATCH_TRANSFER_REQUESTED": "{actor} asked to move a student to another batch",
    "BATCH_TRANSFER_REJECTED": "{actor} turned down a request to move a student",
    "BATCH_CAPACITY_DECIDED": "{actor} decided a request for more seats",
    "SESSION_CREATED": "{actor} scheduled a class: {new.title}",
    "SESSION_UPDATED": "{actor} changed the class {target}",
    "SESSION_RESCHEDULED": "{actor} moved the class {target}",
    "SESSION_CANCELLED": "{actor} cancelled the class {target}",
    "SESSION_CONFIRMED": "{actor} confirmed the class {target}",
    "SESSION_DELIVERED": "{actor} recorded the class {target} as taken",
    "SESSION_NOTES_SAVED": "{actor} saved the class notes of {target}",
    "SESSION_COVER_APPLIED": "{actor} arranged cover for the class {target}",
    "SESSION_PERSON_ADDED": "{actor} added a person to the class {target}",
    "SESSION_PERSON_REMOVED": "{actor} removed a person from the class {target}",
    "MEET_LINK_SET": "{actor} set the Meet link of the class {target}",
    "ATTENDANCE_MARKED": "{actor} marked attendance for the class {target}",
    "ATTENDANCE_CORRECTION_REQUESTED": "{actor} asked to correct an attendance entry",
    "ATTENDANCE_CORRECTION_DECIDED": "{actor} decided an attendance correction",
    "RECOVERY_REQUESTED": "{actor} asked to make up a missed class",
    "RECOVERY_DECIDED": "{actor} decided a make-up request",
    "RECOVERY_COMPLETED": "{actor} marked a make-up as done",
    # course outlines (the old CURRICULUM_* actions stay for the history written before db/121) and content
    "COURSE_OUTLINE_CHANGED": "{actor} changed {target}: {new.change}",
    "COMPONENT_EQUIVALENCE_REVIEWED": "{actor} recorded the equivalence review of a combo track",
    "LIBRARY_MODULE_SAVED": "{actor} saved a module to the library",
    "LIBRARY_VERSION_SAVED": "{actor} saved a new version of a library module",
    "CURRICULUM_CREATED": "{actor} started the curriculum {new.version_label}",
    "CURRICULUM_UPDATED": "{actor} changed the curriculum {target}",
    "CURRICULUM_DELETED": "{actor} discarded a draft curriculum",
    "CURRICULUM_SUBMITTED": "{actor} sent the curriculum {target} for approval",
    "CURRICULUM_APPROVED": "{actor} approved the curriculum {target}",
    "CURRICULUM_RETURNED": "{actor} sent the curriculum {target} back",
    "CURRICULUM_ACTIVATED": "{actor} made the curriculum {target} the active one",
    "CURRICULUM_RETIRED": "{actor} retired the curriculum {target}",
    "CURRICULUM_HOURS_VERIFIED": "{actor} checked the hours of the curriculum {target}",
    "CURRICULUM_MAPPING_RELEASED": "{actor} released students and batches to the new curriculum {target}",
    "CONTENT_CREATED": "{actor} added the content {new.title}",
    "CONTENT_UPDATED": "{actor} changed a content item",
    "CONTENT_SUBMITTED": "{actor} sent a content item for review",
    "CONTENT_REVIEWED": "{actor} reviewed a content item ({new.status})",
    "CONTENT_RELEASED": "{actor} released a content item to a batch",
    "CONTENT_RETIRED": "{actor} retired a content item",
    "CONTENT_VERSION_ADDED": "{actor} added a new version of a content item",
    # recordings
    "RECORDING_REGISTERED": "{actor} registered a recording",
    "RECORDING_RELEASED": "{actor} released a recording to students",
    "RECORDING_HELD": "{actor} held back a recording",
    "RECORDING_PARTIAL": "{actor} marked a recording as partial",
    "RECORDING_UNAVAILABLE": "{actor} marked a recording as unavailable",
    "RECORDING_PROCESSING": "{actor} put a recording back to processing",
    "RECORDING_UPDATED": "{actor} changed a recording",
    "RECORDING_EXCEPTION_RAISED": "{actor} raised a recording problem: {new.issue}",
    # completion, certificates
    "COMPLETION_REVIEW_OPENED": "{actor} started a completion review",
    "COMPLETION_RECOMMENDED": "{actor} recommended a completion decision ({new.recommendation})",
    "COMPLETION_DECIDED": "{actor} decided a completion review ({new.decision})",
    "CERTIFICATE_ENTRY_CREATED": "A certificate entry was created for {new.holder_name}",
    "CERTIFICATE_ELIGIBILITY_OPENED": "{actor} opened the eligibility review of a certificate",
    "CERTIFICATE_RECOMMENDED": "{actor} recommended a certificate for approval",
    "CERTIFICATE_APPROVED": "{actor} approved a certificate",
    "CERTIFICATE_ISSUED": "{actor} issued the certificate {new.certificate_number}",
    "CERTIFICATE_REISSUED": "{actor} issued the certificate {new.certificate_number} again",
    "CERTIFICATE_REVOKED": "{actor} revoked the certificate {new.certificate_number}",
    "CERTIFICATE_REINSTATED": "{actor} reinstated a certificate",
    "CERTIFICATE_RETURNED": "{actor} sent a certificate back",
    "CERTIFICATE_DOWNLOADED": "{actor} downloaded the certificate {new.certificate_number}",
    "CERTIFICATE_CORRECTION_REQUESTED": "{actor} asked for a certificate to be corrected",
    "CERTIFICATE_CORRECTION_APPROVED": "{actor} approved a certificate correction",
    "CERTIFICATE_CORRECTION_REJECTED": "{actor} turned down a certificate correction",
    "CERTIFICATE_REVOCATION_REQUESTED": "{actor} asked for a certificate to be revoked",
    "CERTIFICATE_REVOCATION_APPROVED": "{actor} approved revoking a certificate",
    "CERTIFICATE_REVOCATION_REJECTED": "{actor} turned down revoking a certificate",
    "CERTIFICATE_FINANCIAL_EXCEPTION_REQUESTED": "{actor} asked to issue a certificate with fees still unpaid",
    "CERTIFICATE_FINANCIAL_EXCEPTION_APPROVED": "{actor} allowed a certificate with fees still unpaid",
    "CERTIFICATE_FINANCIAL_EXCEPTION_REJECTED": "{actor} refused a certificate while fees are unpaid",
    "RECEIPT_DOWNLOADED": "{actor} downloaded a receipt",
    # support, access, career
    "SUPPORT_ASSIGNED": "{actor} assigned a support request",
    "SUPPORT_ESCALATED": "{actor} escalated a support request",
    "SUPPORT_REOPENED": "{actor} reopened a support request",
    "SUPPORT_RESOLVED": "{actor} resolved a support request",
    "SUPPORT_ATTACHMENT_DOWNLOADED": "{actor} opened an attachment on a support request",
    "ACCESS_EXTENSION_REQUESTED": "{actor} asked for more time to watch recordings",
    "ACCESS_EXTENSION_RECOMMENDED": "{actor} recommended a decision on an access extension ({new.recommended_decision})",
    "ACCESS_EXTENSION_RECOMMENDATION_REVISED": "{actor} changed their recommendation on an access extension",
    "ACCESS_EXTENSION_DECIDED": "{actor} decided an access extension ({new.status})",
    "CAREER_OPT_IN": "{actor} joined the career programme",
    "CAREER_OPT_OUT": "{actor} left the career programme",
    "CAREER_CONSENT_GIVEN": "{actor} agreed to share their profile with employers",
    "CAREER_CONSENT_WITHDRAWN": "{actor} stopped sharing their profile with employers",
    "OPPORTUNITY_CREATED": "{actor} added the job {new.title}",
    "OPPORTUNITY_UPDATED": "{actor} changed a job listing",
    "OPPORTUNITY_STATUS": "{actor} changed the status of a job listing ({new.status})",
    "APPLICATION_SUBMITTED": "{actor} applied for a job",
    "APPLICATION_STATUS": "{actor} moved a job application on ({new.status})",
    "APPLICATION_WITHDRAWN": "{actor} withdrew a job application",
    "CV_UPLOADED": "{actor} uploaded a CV",
    "CV_REVIEWED": "{actor} reviewed a CV",
    "OUTCOME_RECORDED": "{actor} recorded a placement outcome ({new.type})",
    # student requests, assessments
    "ENROLMENT_JOINED": "{actor} recorded a student's joining date",
    "SLOT_PREFERENCE_STATUS": "{actor} updated a preferred class slot ({new.status})",
    "MATERIAL_CHANGE_PROPOSED": "{actor} proposed a change to a batch's teaching days or times",
    "MATERIAL_CHANGE_DECIDED": "{actor} decided a change to a batch",
    "MATERIAL_CHANGE_RESPONSE": "A student answered a change to their batch ({new.response})",
    "MATERIAL_CHANGE_APPLIED": "A batch change was applied",
    "MATERIAL_CHANGE_WITHDRAWN": "{actor} withdrew a proposed batch change",
    "create": "{actor} created a {entity}",
    "update": "{actor} changed a {entity}",
    "release": "{actor} released a {entity} to students",
    "publish": "{actor} published results",
    "close": "{actor} closed a {entity}",
    "approve": "{actor} approved a {entity}",
    "retire": "{actor} retired a {entity}",
    "withdraw": "{actor} withdrew a {entity}",
    "moderate": "{actor} adjusted a result",
    "set_questions": "{actor} set the questions of a test",
}

ENTITY_NAMES = {
    "assignment": "assignment", "test": "test", "question": "question", "result": "result", "class_session": "class", "batch": "batch",
    "user": "person", "student": "student", "certificate": "certificate", "curriculum_version": "curriculum version", "course": "course",
    "calendar_closure": "calendar entry", "ai_feature_control": "AI switch", "integration": "connection", "security_control": "security setting",
    "crm_event": "CRM update", "exception": "issue", "enrolment": "enrolment", "content_item": "content item", "recording": "recording",
}

# The three preset filters on the Audit log: which actions each one shows
PRESETS = {
    "accounts": ("USER_CREATED", "USER_UPDATED", "USER_DEACTIVATED", "USER_REACTIVATED", "USER_UNLOCKED", "PASSWORD_RESET", "PASSWORD_CHANGED",
                 "PASSWORD_RESET_CODE_REQUESTED", "PASSWORD_RESET_WITH_CODE", "STAFF_INVITE_SENT", "STAFF_INVITE_ACCEPTED", "ACCOUNT_ACTIVATED",
                 "ACTIVATION_ISSUED", "ACTIVATION_REISSUED", "STUDENT_SUSPENDED", "STUDENT_REACTIVATED", "STUDENT_SESSIONS_REVOKED",
                 "STUDENT_EMAIL_CHANGED", "OTHER_SESSIONS_REVOKED", "SESSION_REVOKED", "EMAIL_CHANGE_CODE_REQUESTED"),
    "roles": ("SCOPE_GRANTED", "SCOPE_REVOKED", "USER_CREATED", "USER_DEACTIVATED", "USER_REACTIVATED"),
    "integrations": ("INTEGRATION_UPDATED", "SECURITY_CONTROL_UPDATED", "AI_DISABLED", "AI_RESTORED", "AI_BUDGET_APPROVED", "CRM_EVENT_RETRIED"),
}
PRESET_LABELS = {"accounts": "Accounts", "roles": "Roles", "integrations": "Integrations"}


def humanise(action: str) -> str:
    """USER_CREATED -> "User created" for an action with no template."""
    return action.replace("_", " ").capitalize()


def _fill(template: str, values: dict) -> str:
    def take(match: re.Match) -> str:
        return str(values.get(match.group(1), "") or "")

    text = re.sub(r"\{([a-z_]+(?:\.[a-z_]+)?)\}", take, template)
    text = re.sub(r"\s*\(\s*\)", "", text)  # a bracket left empty because its value was missing
    return re.sub(r"\s{2,}", " ", text).strip().rstrip(":")


def sentence(entry: AuditLog, actor_name: str | None, target: str | None) -> str:
    template = SENTENCES.get(entry.action)
    actor = actor_name or "The system"
    if template is None:
        return f"{humanise(entry.action)} by {actor}" if actor_name else humanise(entry.action)
    values = {"actor": actor, "target": target or f"{ENTITY_NAMES.get(entry.entity_type, entry.entity_type.replace('_', ' '))} {entry.entity_id}",
              "entity": ENTITY_NAMES.get(entry.entity_type, entry.entity_type.replace("_", " ")), "reason": entry.reason or ""}
    for prefix, snapshot in (("new", entry.new_values), ("old", entry.old_values)):
        for key, value in (snapshot or {}).items():
            if isinstance(value, (str, int, float)):
                values[f"{prefix}.{key}"] = value
    text = _fill(template, values)
    return text[:1].upper() + text[1:]


# ---------------------------------------------------------------- what an entry is about

def _ids(entries: list[AuditLog], entity_type: str) -> set[str]:
    return {e.entity_id for e in entries if e.entity_type == entity_type}


def _int_ids(ids: set[str]) -> list[int]:
    return [int(i) for i in ids if i.isdigit()]


def resolve_targets(entries: list[AuditLog]) -> dict[tuple[str, str], dict]:
    """`(entity_type, entity_id) -> {label, link}` for the records an admin can open, in a handful of queries for the whole page.

    `link` is `{to, search}` for the router, or None when there is no screen for the record in the Super Admin's workspace.
    """
    found: dict[tuple[str, str], dict] = {}

    def add(kind: str, key, label: str, link: dict | None) -> None:
        found[(kind, str(key))] = {"label": label, "link": link}

    users = _int_ids(_ids(entries, "user"))
    if users:
        for u in db.session.execute(select(User).where(User.user_id.in_(users))).scalars():
            add("user", u.user_id, u.full_name, {"to": "/admin/users", "search": {"q": u.email or u.full_name}} if u.student_id is None else None)
    students = _int_ids(_ids(entries, "student"))
    if students:
        for s in db.session.execute(select(Student).where(Student.student_id.in_(students))).scalars().unique():
            add("student", s.student_id, f"{s.full_name} ({s.student_code})", {"to": "/admin/students/$id", "params": {"id": s.student_id}})
    for code, name in db.session.execute(select(Integration.integration_code, Integration.integration_name)
                                         .where(Integration.integration_code.in_(_ids(entries, "integration")))).all():
        add("integration", code, name, {"to": "/admin/setup", "search": {}})
    for code, title in db.session.execute(select(SecurityControl.control_code, SecurityControl.title)
                                          .where(SecurityControl.control_code.in_(_ids(entries, "security_control")))).all():
        add("security_control", code, title, {"to": "/admin/setup", "search": {}})
    closures = _int_ids(_ids(entries, "calendar_closure"))
    if closures:
        for c in db.session.execute(select(CalendarClosure).where(CalendarClosure.closure_id.in_(closures))).scalars().unique():
            add("calendar_closure", c.closure_id, f"{c.title} ({c.starts_on:%d %b}" + (f" to {c.ends_on:%d %b}" if c.ends_on != c.starts_on else "") + ")",
                {"to": "/admin/calendar", "search": {}})
    controls = _int_ids(_ids(entries, "ai_feature_control"))
    if controls:
        for c in db.session.execute(select(AiFeatureControl).where(AiFeatureControl.control_id.in_(controls))).scalars().unique():
            add("ai_feature_control", c.control_id, {"All": "all AI", "Student": "the student assistant", "Staff": "the staff assistant"}[c.audience],
                {"to": "/admin/ai-controls", "search": {}})
    events = _int_ids(_ids(entries, "crm_event"))
    if events:
        for e in db.session.execute(select(CrmEvent).where(CrmEvent.crm_event_id.in_(events))).scalars():
            add("crm_event", e.crm_event_id, e.event_id, {"to": "/admin/crm-sync", "search": {"event": e.crm_event_id}})
    batches = _int_ids(_ids(entries, "batch"))
    if batches:
        for b in db.session.execute(select(Batch).where(Batch.batch_id.in_(batches))).scalars().unique():
            add("batch", b.batch_id, b.batch_code, {"to": "/branch/batches/$id", "params": {"id": b.batch_id}})
    sessions = _int_ids(_ids(entries, "class_session"))
    if sessions:
        for s in db.session.execute(select(ClassSession).where(ClassSession.session_id.in_(sessions))).scalars().unique():
            add("class_session", s.session_id, s.session_code, {"to": "/branch/schedule", "search": {"session": s.session_id}})
    courses = _int_ids(_ids(entries, "course"))
    if courses:
        for c in db.session.execute(select(Course).where(Course.course_id.in_(courses))).scalars().unique():
            add("course", c.course_id, f"the outline of {c.title}", {"to": "/admin/courses/$id", "params": {"id": c.course_id}})
    for entry in entries:
        if entry.entity_type == "exception":
            add("exception", entry.entity_id, "an issue", {"to": "/admin/issues", "search": {}})
    return found


def annotate(entries: list[AuditLog], actor_names: dict[int, str]) -> list[dict]:
    """Each entry as stored plus `sentence`, `target` (its name) and `link`."""
    targets = resolve_targets(entries)
    out = []
    for entry in entries:
        target = targets.get((entry.entity_type, entry.entity_id))
        out.append({**entry.to_dict(), "sentence": sentence(entry, actor_names.get(entry.actor_user_id), target["label"] if target else None),
                    "target": target["label"] if target else None, "link": target["link"] if target else None})
    return out


def annotate_loaded(entries: list[AuditLog]) -> list[dict]:
    """`annotate` for entries read without their actors' names (the recent history on a student's page)."""
    ids = {e.actor_user_id for e in entries if e.actor_user_id}
    names = dict(db.session.execute(select(User.user_id, User.full_name).where(User.user_id.in_(ids))).all()) if ids else {}
    return annotate(entries, names)
