"""The student's Certificates screen (UX phase U10): one card per course with a three-step tracker, the blocker in plain terms,
and the certificate PDF.

  * `get_overview()` adds `cards` to what `GET /me/certificates` always returned. A card holds the certificate's steps
    (Course completed -> Review -> Issued, each done / current / todo) and at most one `blocker`: a code with parameters, so the
    screen words it (and translates it); the server does not send sentences.
  * `certificate_pdf(id)` renders the issued version for its owner only.
"""
from flask import current_app

from config.database import db
from models import Certificate, Enrolment
from repositories import certificates as certificates_repo
from repositories import students as students_repo
from services import audit, certificates, pdf
from services.context import current_user
from services.errors import BusinessRule, NotFound

UNUSABLE_STATUSES = ("Withdrawn", "Provisioning Pending")
STEP_KEYS = ("completed", "review", "issued")
# certificate status -> (state of Course completed, Review, Issued)
STEPS = {
    "Not Yet Eligible": ("current", "todo", "todo"),
    "Eligibility Review": ("done", "current", "todo"),
    "Awaiting Approval": ("done", "current", "todo"),
    "Approved for Issue": ("done", "done", "current"),
    "Issued": ("done", "done", "done"),
    "Revoked": ("done", "done", "done"),
}
BEFORE_ISSUE = ("Eligibility Review", "Awaiting Approval", "Approved for Issue")


def _student_id() -> int:
    student_id = current_user().student_id
    if student_id is None:
        raise NotFound("This login has no student record")
    return student_id


def verify_url(number: str) -> str | None:
    """The public verification address of a certificate number, when the LMS knows its own address."""
    base = current_app.config.get("PUBLIC_BASE_URL")
    return f"{base.rstrip('/')}/verify/{number}" if base else None


def _fee(enrolment: Enrolment, certificate_type: str) -> dict:
    clearance = certificates.fee_clearance_for(enrolment, certificate_type)
    return {"state": clearance["state"], "cleared": clearance["cleared"], "balance": clearance["balance"]}


def _blocker(enrolment: Enrolment, certificate: Certificate | None, status: str, fee: dict | None) -> dict | None:
    """The one thing the student should know about: what the certificate is waiting for."""
    if certificate is None and not certificates.has_completion_rule(enrolment):
        return {"code": "config_pending", "params": {}}
    if status == "Issued":
        return None
    if status == "Revoked":
        return {"code": "revoked", "params": {"reason": certificate.reason if certificate is not None else None}}
    if status == "Not Yet Eligible":
        internship = certificate is not None and certificate.certificate_type == "Internship Certificate"
        return {"code": "internship_evidence" if internship else "not_completed", "params": {}}
    if fee is not None and not fee["cleared"]:  # completed, so the fee is what holds it back (checked at recommendation and at issue)
        if fee["state"] == "Outstanding":
            return {"code": "fee_outstanding", "params": {"balance": fee["balance"]}}
        return {"code": "fee_unknown", "params": {}}
    return {"code": "ready_to_issue" if status == "Approved for Issue" else "in_review", "params": {}}


def _card(enrolment: Enrolment, certificate: Certificate | None, certificate_type: str) -> dict:
    status = certificate.status if certificate is not None else "Not Yet Eligible"
    if status == "Not Yet Eligible" and certificate_type == certificates.COMPLETION_CERTIFICATE and enrolment.status == "Completed":
        status = "Eligibility Review"  # the course is finished; the register is about to open its review
    fee = _fee(enrolment, certificate_type) if status in BEFORE_ISSUE else None
    issued = certificate is not None and certificate.status == "Issued"
    return {
        "key": f"c{certificate.certificate_id}" if certificate is not None else f"e{enrolment.enrolment_id}-{certificate_type}",
        "enrolment": enrolment.to_summary(),
        "course": {"course_id": enrolment.course.course_id, "course_code": enrolment.course.course_code, "title": enrolment.course.title},
        "certificate_type": certificate_type,
        "certificate": None if certificate is None else {
            "certificate_id": certificate.certificate_id, "certificate_number": certificate.certificate_number,
            "version": certificate.version, "status": certificate.status, "issue_date": certificate.issue_date,
            "holder_name": certificate.holder_name,
        },
        "steps": [{"key": key, "state": state} for key, state in zip(STEP_KEYS, STEPS[status])],
        "blocker": _blocker(enrolment, certificate, status, fee),
        "fee": fee,
        "can_download": issued,
        "verify_path": f"/verify/{certificate.certificate_number}" if issued else None,
    }


def cards() -> list[dict]:
    """One card per course: the live register entries of each usable enrolment, or an empty Course Completion card when the
    register has none yet (the course is still being studied)."""
    result = []
    for enrolment in students_repo.enrolments_of_student(_student_id()):
        if enrolment.status in UNUSABLE_STATUSES:
            continue
        entries = certificates_repo.live_entries(enrolment.enrolment_id)
        if not entries:
            result.append(_card(enrolment, None, certificates.COMPLETION_CERTIFICATE))
        result.extend(_card(enrolment, entry, entry.certificate_type) for entry in entries)
    return result


def get_overview() -> dict:
    return {**certificates.my_certificates(), "cards": cards()}


def _pdf_filename(certificate: Certificate) -> str:
    return f"{certificate.certificate_number}.pdf" if certificate.version == 1 else f"{certificate.certificate_number}-v{certificate.version}.pdf"


def certificate_pdf(certificate_id: int) -> tuple[bytes, str]:
    """The PDF of an Issued certificate, drawn from that version's own data. Only its owner may download it; a certificate that
    is not issued, was revoked or was replaced by a corrected version has no PDF."""
    certificate = certificates_repo.get_certificate(certificate_id)
    if certificate is None or certificate.student_id != _student_id():
        raise NotFound("Certificate not found")
    if certificate.status == "Revoked":
        raise BusinessRule("This certificate was revoked, so it can no longer be downloaded")
    if certificate.status == "Superseded":
        raise BusinessRule("A corrected version replaced this certificate. Download the current version instead")
    if certificate.status != "Issued":
        raise BusinessRule("This certificate has not been issued yet")
    content = pdf.render_certificate({
        "holder_name": certificate.holder_name,
        "course_title": certificate.course.title,
        "certificate_type": certificate.certificate_type,
        "certificate_number": certificate.certificate_number,
        "version": certificate.version,
        "issue_date": certificate.issue_date,
        "branch_name": certificate.branch.branch_name,
        "verify_url": verify_url(certificate.certificate_number),
    })
    audit.record("CERTIFICATE_DOWNLOADED", "certificate", certificate.certificate_id, new={"certificate_number": certificate.certificate_number,
                 "version": certificate.version}, branch_id=certificate.branch_id)
    db.session.flush()
    return content, _pdf_filename(certificate)
