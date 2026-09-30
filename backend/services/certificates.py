"""LMS Certificate Register: eligibility, recommendation, approval, issue, reissue, revoke, and public verification.

Flow: Not Yet Eligible -> (Complete completion decision) Eligibility Review -> (Academic Coordinator recommends)
Awaiting Approval -> (Branch Manager approves) Approved for Issue -> (issue) Issued. The number NIT-CERT-YYYY-NNNNNN is
allocated by the database at first issue and kept across reissues; a reissue is a new version and supersedes the earlier one.
The Super Admin can revoke an issued certificate. Every change is audited.
"""
from config.database import db
from models import Certificate, CompletionReview, Enrolment
from repositories import certificates as certificates_repo
from repositories import settings as settings_repo
from repositories import students as students_repo
from repositories import users as users_repo
from repositories.common import paginate
from services import audit, scope
from services.context import current_user
from services.errors import BusinessRule, Conflict, Forbidden, NotFound
from services.notifications import notify

COMPLETION_CERTIFICATE = "Course Completion Certificate"
COMPLIMENTARY_PENDING = "Configuration Pending: completion rule not configured for complimentary offer"

REVIEWERS = ("ACADEMIC_COORDINATOR", "SUPER_ADMIN")
APPROVERS = ("BRANCH_MANAGER", "SUPER_ADMIN")
ISSUERS = ("BRANCH_MANAGER", "ACADEMIC_COORDINATOR", "SUPER_ADMIN")
RE_ISSUERS = ("BRANCH_MANAGER", "SUPER_ADMIN")


def complimentary_rule_configured() -> bool:
    return settings_repo.get("complimentary_completion_rule_configured", False) is True


def has_completion_rule(enrolment: Enrolment) -> bool:
    """False for a complimentary offer whose completion rule is not configured yet."""
    return enrolment.kind != "Complimentary" or complimentary_rule_configured()


def _snapshot(certificate: Certificate) -> dict:
    return {"status": certificate.status, "version": certificate.version, "certificate_number": certificate.certificate_number,
            "certificate_type": certificate.certificate_type, "holder_name": certificate.holder_name}


def _student_user_ids(student_id: int) -> list[int]:
    user = users_repo.get_by_student_id(student_id)
    return [user.user_id] if user else []


def _require_role(certificate: Certificate, *role_codes: str) -> None:
    """404 outside the user's branches, 403 when they hold none of the roles at the certificate's branch."""
    scope.require_branch(certificate.branch_id)
    if not current_user().has_role(*role_codes, branch_id=certificate.branch_id):
        raise Forbidden("You don't have access to this action")


def actions_for(certificate: Certificate) -> list[str]:
    """What the current user may do to this entry right now (the UI shows exactly these buttons)."""
    user = current_user()
    at_branch = certificate.branch_id

    def can(*roles: str) -> bool:
        return user.has_role(*roles, branch_id=at_branch)

    match certificate.status:
        case "Eligibility Review" if can(*REVIEWERS):
            return ["recommend"]
        case "Awaiting Approval" if can(*APPROVERS):
            return ["approve", "return"]
        case "Approved for Issue" if can(*ISSUERS):
            return ["issue"]
        case "Issued":
            return [a for a, allowed in (("reissue", can(*RE_ISSUERS)), ("revoke", can("SUPER_ADMIN"))) if allowed]
    return []


# ---------------------------------------------------------------- creating entries

def ensure_register_entry(enrolment: Enrolment, certificate_type: str = COMPLETION_CERTIFICATE) -> Certificate | None:
    """The enrolment's live register entry of this type, created as Not Yet Eligible when missing.

    None for a complimentary offer without a configured completion rule: it shows Configuration Pending instead of a row.
    """
    if not has_completion_rule(enrolment):
        return None
    existing = certificates_repo.live_entry(enrolment.enrolment_id, certificate_type)
    if existing is not None:
        return existing
    student = students_repo.get_student(enrolment.student_id)
    certificate = Certificate(certificate_type=certificate_type, enrolment_id=enrolment.enrolment_id, student_id=enrolment.student_id,
                              course_id=enrolment.course_id, branch_id=enrolment.service_branch_id, holder_name=student.full_name)
    db.session.add(certificate)
    db.session.flush()
    audit.record("CERTIFICATE_ENTRY_CREATED", "certificate", certificate.certificate_id, new=_snapshot(certificate),
                 branch_id=certificate.branch_id)
    return certificate


def open_eligibility(enrolment: Enrolment, review: CompletionReview) -> list[Certificate]:
    """A Complete completion decision opens eligibility (Not Yet Eligible -> Eligibility Review) for every live entry of the
    enrolment (e.g. an Internship Certificate added earlier), or for a new Course Completion entry when there is none."""
    entries = certificates_repo.live_entries(enrolment.enrolment_id) or [ensure_register_entry(enrolment)]
    opened = []
    for certificate in (c for c in entries if c is not None and c.status == "Not Yet Eligible"):
        old = _snapshot(certificate)
        certificate.status = "Eligibility Review"
        certificate.completion_review_id = review.review_id
        db.session.flush()
        audit.record("CERTIFICATE_ELIGIBILITY_OPENED", "certificate", certificate.certificate_id, old=old, new=_snapshot(certificate),
                     branch_id=certificate.branch_id)
        notify(category="Certificate", title=f"Certificate eligibility to review: {enrolment.course.course_code}",
               body=f"{certificate.holder_name}'s completion was confirmed. Review the {certificate.certificate_type} entry and recommend it for approval.",
               link="/academic/certificates", role_code="ACADEMIC_COORDINATOR", branch_id=certificate.branch_id,
               event_key=f"certificate-eligibility:{certificate.certificate_id}", action_required=True)
        opened.append(certificate)
    return opened


def create_entry(enrolment_id: int, certificate_type: str) -> Certificate:
    """Academic Coordinator adds a register entry (for example an Internship Certificate) for an enrolment."""
    enrolment = students_repo.get_enrolment(enrolment_id)
    if enrolment is None:
        raise NotFound("Enrolment not found")
    scope.require_branch(enrolment.service_branch_id)
    if not current_user().has_role(*REVIEWERS, branch_id=enrolment.service_branch_id):
        raise Forbidden("You don't have access to this action")
    if not has_completion_rule(enrolment):
        raise BusinessRule(COMPLIMENTARY_PENDING)
    if certificates_repo.live_entry(enrolment_id, certificate_type) is not None:
        raise Conflict(f"{certificate_type} already has a register entry for this enrolment")
    if enrolment.status not in ("Active", "Completed"):
        raise BusinessRule(f"Enrolment {enrolment.enrolment_code} is '{enrolment.status}'; only a running or completed enrolment can have a certificate entry")
    certificate = ensure_register_entry(enrolment, certificate_type)
    if enrolment.status == "Completed":
        certificate.status = "Eligibility Review"
        db.session.flush()
    return certificate


# ---------------------------------------------------------------- moving an entry along

def _get(certificate_id: int) -> Certificate:
    certificate = certificates_repo.get_certificate(certificate_id)
    if certificate is None:
        raise NotFound("Certificate not found")
    return certificate


def recommend(certificate_id: int, note: str | None) -> Certificate:
    certificate = _get(certificate_id)
    _require_role(certificate, *REVIEWERS)
    _expect_status(certificate, "Eligibility Review")
    old = _snapshot(certificate)
    certificate.status = "Awaiting Approval"
    certificate.recommended_by = current_user().user_id
    certificate.recommended_at = db.func.now()
    db.session.flush()
    db.session.refresh(certificate)
    audit.record("CERTIFICATE_RECOMMENDED", "certificate", certificate.certificate_id, old=old, new=_snapshot(certificate),
                 reason=note, branch_id=certificate.branch_id)
    notify(category="Certificate", title=f"Certificate awaiting your approval: {certificate.holder_name}",
           body=f"{certificate.certificate_type} for {certificate.course.course_code} was recommended by the Academic Coordinator.",
           link="/branch/reports", role_code="BRANCH_MANAGER", branch_id=certificate.branch_id,
           event_key=f"certificate-recommended:{certificate.certificate_id}", action_required=True)
    return certificate


def return_to_review(certificate_id: int, reason: str) -> Certificate:
    certificate = _get(certificate_id)
    _require_role(certificate, *APPROVERS)
    _expect_status(certificate, "Awaiting Approval")
    old = _snapshot(certificate)
    certificate.status = "Eligibility Review"
    certificate.recommended_by = None
    certificate.recommended_at = None
    db.session.flush()
    db.session.refresh(certificate)
    audit.record("CERTIFICATE_RETURNED", "certificate", certificate.certificate_id, old=old, new=_snapshot(certificate),
                 reason=reason, branch_id=certificate.branch_id)
    notify(category="Certificate", title=f"Certificate returned for review: {certificate.holder_name}", body=reason,
           link="/academic/certificates", role_code="ACADEMIC_COORDINATOR", branch_id=certificate.branch_id,
           event_key=f"certificate-returned:{certificate.certificate_id}:{certificate.updated_at.isoformat()}", action_required=True)
    return certificate


def approve(certificate_id: int) -> Certificate:
    certificate = _get(certificate_id)
    _require_role(certificate, *APPROVERS)
    _expect_status(certificate, "Awaiting Approval")
    user = current_user()
    if certificate.recommended_by == user.user_id:
        raise BusinessRule("Approval needs a different person than the one who recommended the certificate")
    old = _snapshot(certificate)
    certificate.status = "Approved for Issue"
    certificate.approved_by = user.user_id
    certificate.approved_at = db.func.now()
    db.session.flush()
    db.session.refresh(certificate)
    audit.record("CERTIFICATE_APPROVED", "certificate", certificate.certificate_id, old=old, new=_snapshot(certificate),
                 branch_id=certificate.branch_id)
    notify(category="Certificate", title=f"Certificate approved for issue: {certificate.holder_name}",
           body="The number is allocated when the certificate is issued.", link="/academic/certificates",
           role_code="ACADEMIC_COORDINATOR", branch_id=certificate.branch_id,
           event_key=f"certificate-approved:{certificate.certificate_id}", action_required=True)
    return certificate


def issue(certificate_id: int) -> Certificate:
    """Issue an approved certificate: the database allocates NIT-CERT-YYYY-NNNNNN and the issue date."""
    certificate = _get(certificate_id)
    _require_role(certificate, *ISSUERS)
    _expect_status(certificate, "Approved for Issue")
    old = _snapshot(certificate)
    certificate.status = "Issued"
    certificate.issued_by = current_user().user_id
    db.session.flush()
    db.session.refresh(certificate)
    audit.record("CERTIFICATE_ISSUED", "certificate", certificate.certificate_id, old=old, new=_snapshot(certificate),
                 branch_id=certificate.branch_id)
    _tell_student(certificate, f"Your certificate was issued: {certificate.certificate_number}",
                  f"{certificate.certificate_type} for {certificate.course.title}.", "issued")
    return certificate


def reissue(certificate_id: int, reason: str, holder_name: str | None) -> Certificate:
    """A corrected copy (v2, v3 ...) under the same number; the earlier version becomes Superseded and stays on record."""
    previous = _get(certificate_id)
    _require_role(previous, *RE_ISSUERS)
    _expect_status(previous, "Issued")
    user = current_user()
    old = _snapshot(previous)
    previous.status = "Superseded"
    db.session.flush()
    certificate = Certificate(
        certificate_type=previous.certificate_type, version=previous.version + 1, status="Issued", enrolment_id=previous.enrolment_id,
        student_id=previous.student_id, course_id=previous.course_id, branch_id=previous.branch_id,
        holder_name=holder_name or previous.holder_name, completion_review_id=previous.completion_review_id, reason=reason,
        recommended_by=previous.recommended_by, recommended_at=previous.recommended_at, approved_by=previous.approved_by,
        approved_at=previous.approved_at, issued_by=user.user_id, supersedes_certificate_id=previous.certificate_id)
    db.session.add(certificate)
    db.session.flush()
    db.session.refresh(certificate)
    audit.record("CERTIFICATE_REISSUED", "certificate", certificate.certificate_id, old=old, new=_snapshot(certificate),
                 reason=reason, branch_id=certificate.branch_id)
    _tell_student(certificate, f"Your certificate was reissued: {certificate.certificate_number} (v{certificate.version})", reason, "reissued")
    return certificate


def revoke(certificate_id: int, reason: str) -> Certificate:
    certificate = _get(certificate_id)
    _require_role(certificate, "SUPER_ADMIN")
    _expect_status(certificate, "Issued")
    old = _snapshot(certificate)
    certificate.status = "Revoked"
    certificate.reason = reason
    certificate.revoked_by = current_user().user_id
    certificate.revoked_at = db.func.now()
    db.session.flush()
    db.session.refresh(certificate)
    audit.record("CERTIFICATE_REVOKED", "certificate", certificate.certificate_id, old=old, new=_snapshot(certificate),
                 reason=reason, branch_id=certificate.branch_id)
    _tell_student(certificate, f"Your certificate was revoked: {certificate.certificate_number}", reason, "revoked")
    notify(category="Certificate", title=f"Certificate revoked: {certificate.certificate_number}", body=reason,
           link="/branch/reports", role_code="BRANCH_MANAGER", branch_id=certificate.branch_id,
           event_key=f"certificate-revoked-bm:{certificate.certificate_id}")
    return certificate


def _expect_status(certificate: Certificate, status: str) -> None:
    if certificate.status != status:
        raise BusinessRule(f"The certificate is '{certificate.status}'; this step needs it to be '{status}'")


def _tell_student(certificate: Certificate, title: str, body: str, verb: str) -> None:
    notify(category="Certificate", title=title, body=body, link="/certificates", branch_id=certificate.branch_id,
           recipient_user_ids=_student_user_ids(certificate.student_id),
           event_key=f"certificate-{verb}:{certificate.certificate_id}")


# ---------------------------------------------------------------- reads

def list_register(filters: dict, page: int, per_page: int) -> tuple[list[tuple[Certificate, list[str]]], dict]:
    """The Certificate Register of the user's branches (every version, so reissues and revocations stay visible)."""
    branch_ids = scope.visible_branch_ids()
    if branch_ids is not None and not branch_ids:
        raise Forbidden("You don't have access to the certificate register")
    rows, meta = paginate(certificates_repo.register_stmt(filters, branch_ids), page, per_page)
    return [(c, actions_for(c)) for c in rows], meta


def my_certificates() -> dict:
    """The signed-in student's certificates (current versions) and enrolments whose completion rule is not configured."""
    student_id = current_user().student_id
    if student_id is None:
        raise NotFound("This login has no student record")
    rows = list(db.session.scalars(certificates_repo.register_stmt({}, None, student_id)).unique())
    pending = [
        {"enrolment": e.to_summary(), "state": "Configuration Pending",
         "message": "Completion rule not configured for complimentary offer"}
        for e in students_repo.enrolments_of_student(student_id) if e.kind == "Complimentary" and not has_completion_rule(e)
    ]
    return {"certificates": [c for c in rows if c.status != "Superseded"], "configuration_pending": pending}


def get_certificate(certificate_id: int) -> tuple[Certificate, list[Certificate], list[str]]:
    """One entry, its version history (same number) and the user's available actions. A student sees only their own."""
    certificate = _get(certificate_id)
    user = current_user()
    if user.student_id is not None and certificate.student_id == user.student_id:
        actions: list[str] = []
    else:
        scope.require_branch(certificate.branch_id)
        actions = actions_for(certificate)
    history = certificates_repo.versions(certificate.certificate_number) if certificate.certificate_number else [certificate]
    return certificate, history, actions


def verify(number: str) -> Certificate:
    """Public verification by number: the latest version decides the status."""
    certificate = certificates_repo.latest_by_number(number)
    if certificate is None:
        raise NotFound("No certificate with this number")
    return certificate
