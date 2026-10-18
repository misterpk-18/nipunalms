"""Certificate decisions that need an independent approver (Module 22 §5, §7, §8).

Change requests: a correction / reissue (Branch Manager or Super Admin asks; Branch Manager or
Super Admin decides), a revocation or a reinstatement (asked with evidence; Founder / CEO or Super Admin decides). The
certificate stays as it is until the request is approved; approving applies it (services/certificates.py).

Financial-release exceptions: the Branch Manager or Super Admin asks for certificates to go ahead
while the paying admission's fee is not cleared; the Founder / CEO or Super Admin decides. The debt is not waived.
"""
from datetime import datetime, timezone
from decimal import Decimal

from config.database import db
from models import Certificate, CertificateChangeRequest, CertificateFinancialException
from repositories import certificates as certificates_repo
from repositories import students as students_repo
from repositories.common import paginate
from services import approvals, audit, certificates, scope
from services.context import current_user
from services.errors import BusinessRule, Conflict, Forbidden, NotFound, ValidationError
from services.notifications import notify

REQUESTERS = {"Correction": certificates.CORRECTION_REQUESTERS, "Revocation": certificates.REVOCATION_REQUESTERS,
              "Reinstatement": certificates.REVOCATION_REQUESTERS}
DECIDERS = {"Correction": certificates.CORRECTION_APPROVERS, "Revocation": certificates.REVOCATION_APPROVERS,
            "Reinstatement": certificates.REVOCATION_APPROVERS}
NEEDED_STATUS = {"Correction": "Issued", "Revocation": "Issued", "Reinstatement": "Revoked"}
# Where each deciding role works on requests
DECIDER_LINKS = {"BRANCH_MANAGER": "/branch/completion", "SUPER_ADMIN": "/admin/approvals", "FOUNDER_CEO": "/founder/certificates"}

EXCEPTION_REQUESTERS = ("BRANCH_MANAGER",)
EXCEPTION_DECIDERS = ("FOUNDER_CEO", "SUPER_ADMIN")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _notify_deciders(role_codes: tuple[str, ...], branch_id: int, *, title: str, body: str, event_key: str) -> None:
    for role_code in role_codes:
        notify(category="Certificate", title=title, body=body, link=DECIDER_LINKS[role_code], role_code=role_code,
               branch_id=branch_id, event_key=f"{event_key}:{role_code}", action_required=True)


# ---------------------------------------------------------------- change requests

def request_change(certificate_id: int, kind: str, reason: str, evidence: str | None, holder_name: str | None) -> CertificateChangeRequest:
    certificate = certificates_repo.get_certificate(certificate_id)
    if certificate is None:
        raise NotFound("Certificate not found")
    scope.require_branch(certificate.branch_id)
    if not current_user().has_role(*REQUESTERS[kind], branch_id=certificate.branch_id):
        raise Forbidden("You don't have access to this action")
    if certificate.status != NEEDED_STATUS[kind]:
        raise BusinessRule(f"A {kind.lower()} needs an {NEEDED_STATUS[kind]} certificate; this one is {certificate.status}")
    if certificates_repo.pending_request(certificate_id) is not None:
        raise Conflict("This certificate already has a request waiting for a decision")
    if kind != "Correction" and not evidence:
        raise ValidationError("Invalid request data", {"evidence": [f"A {kind.lower()} needs the evidence it rests on"]})
    changes = {}
    if kind == "Correction" and holder_name and holder_name != certificate.holder_name:
        changes["holder_name"] = {"from": certificate.holder_name, "to": holder_name}
    request = CertificateChangeRequest(certificate_id=certificate_id, kind=kind, reason=reason, evidence=evidence, changes=changes,
                                       requested_by=current_user().user_id)
    db.session.add(request)
    db.session.flush()
    audit.record(f"CERTIFICATE_{kind.upper()}_REQUESTED", "certificate", certificate_id, new={"request_id": request.request_id,
                 "changes": changes}, reason=reason, branch_id=certificate.branch_id)
    _notify_deciders(DECIDERS[kind], certificate.branch_id,
                     title=f"Certificate {kind.lower()} to decide: {certificate.certificate_number}",
                     body=f"{certificate.holder_name}: {reason}", event_key=f"certificate-request:{request.request_id}")
    return request


def actions_for_request(request: CertificateChangeRequest) -> list[str]:
    user = current_user()
    if request.status != "Pending" or not approvals.can_decide(request.requested_by):
        return []
    return ["decide"] if user.has_role(*DECIDERS[request.kind], branch_id=request.certificate.branch_id) else []


def list_requests(filters: dict, page: int, per_page: int) -> tuple[list[tuple[CertificateChangeRequest, list[str]]], dict]:
    rows, meta = paginate(certificates_repo.requests_stmt(filters, scope.visible_branch_ids()), page, per_page)
    return [(r, actions_for_request(r)) for r in rows], meta


def decide_request(request_id: int, decision: str, note: str | None) -> CertificateChangeRequest:
    request = certificates_repo.get_request(request_id)
    if request is None:
        raise NotFound("Request not found")
    certificate: Certificate = request.certificate
    scope.require_branch(certificate.branch_id)
    if not current_user().has_role(*DECIDERS[request.kind], branch_id=certificate.branch_id):
        raise Forbidden("You don't have access to this decision")
    if request.status != "Pending":
        raise BusinessRule(f"This request is already {request.status}")
    approvals.require_independent(request.requested_by, message="An independent approver must decide: not the person who asked",
                                  requester=request.requested_by)
    if decision == "Rejected" and not note:
        raise ValidationError("Invalid request data", {"note": ["Give the reason for rejecting the request"]})

    request.status, request.decided_by, request.decided_at, request.decision_note = decision, current_user().user_id, _now(), note
    db.session.flush()
    if decision == "Approved":
        if request.kind == "Correction":
            corrected = certificates.apply_correction(certificate, request.reason, request.changes.get("holder_name", {}).get("to"))
            request.resulting_certificate_id = corrected.certificate_id
        elif request.kind == "Revocation":
            certificates.apply_revocation(certificate, request.reason)
        else:
            certificates.apply_reinstatement(certificate, request.reason)
    audit.record(f"CERTIFICATE_{request.kind.upper()}_{decision.upper()}", "certificate", certificate.certificate_id,
                 new={"request_id": request.request_id, "decision": decision}, reason=note, branch_id=certificate.branch_id)
    notify(category="Certificate", title=f"Certificate {request.kind.lower()} {decision.lower()}: {certificate.certificate_number}",
           body=note or request.reason, link="/branch/completion", recipient_user_ids=[request.requested_by],
           branch_id=certificate.branch_id, event_key=f"certificate-request-decided:{request.request_id}")
    db.session.flush()
    return request


# ---------------------------------------------------------------- financial-release exceptions

def request_exception(certificate_id: int, reason: str) -> CertificateFinancialException:
    """Ask for this certificate's paying admission to be released for certificates while its fee is outstanding."""
    certificate = certificates_repo.get_certificate(certificate_id)
    if certificate is None:
        raise NotFound("Certificate not found")
    scope.require_branch(certificate.branch_id)
    if not current_user().has_role(*EXCEPTION_REQUESTERS, branch_id=certificate.branch_id):
        raise Forbidden("You don't have access to this action")
    clearance = certificates.fee_clearance(certificate)
    if clearance["cleared"]:
        raise BusinessRule(f"No exception is needed: the fee is {clearance['state']}")
    if clearance["state"] == "Not Received":
        raise BusinessRule("The fee status has not been received from the CRM; an exception needs the outstanding amount")
    if certificates_repo.pending_exception(clearance["admission_id"]) is not None:
        raise Conflict("This admission already has an exception waiting for a decision")
    exception = CertificateFinancialException(
        admission_id=clearance["admission_id"], outstanding_amount=Decimal(clearance["balance"]),
        certificate_types=[certificate.certificate_type], reason=reason, requested_by=current_user().user_id)
    db.session.add(exception)
    db.session.flush()
    admission = students_repo.get_admission(clearance["admission_id"])
    audit.record("CERTIFICATE_FINANCIAL_EXCEPTION_REQUESTED", "admission", admission.admission_code,
                 new={"exception_id": exception.exception_id, "outstanding_amount": clearance["balance"]}, reason=reason,
                 branch_id=certificate.branch_id)
    _notify_deciders(EXCEPTION_DECIDERS, certificate.branch_id, title=f"Certificate release exception to decide: {admission.admission_code}",
                     body=f"₹{clearance['balance']} outstanding. {reason}", event_key=f"financial-exception:{exception.exception_id}")
    return exception


def actions_for_exception(exception: CertificateFinancialException) -> list[str]:
    user = current_user()
    if exception.status != "Pending" or user.user_id == exception.requested_by:
        return []
    return ["decide"] if user.has_role(*EXCEPTION_DECIDERS, branch_id=exception.admission.service_branch_id) else []


def list_exceptions(filters: dict, page: int, per_page: int) -> tuple[list[tuple[CertificateFinancialException, list[str]]], dict]:
    rows, meta = paginate(certificates_repo.exceptions_stmt(filters, scope.visible_branch_ids()), page, per_page)
    return [(e, actions_for_exception(e)) for e in rows], meta


def decide_exception(exception_id: int, decision: str, note: str | None) -> CertificateFinancialException:
    exception = certificates_repo.get_exception(exception_id)
    if exception is None:
        raise NotFound("Exception not found")
    branch_id = exception.admission.service_branch_id
    scope.require_branch(branch_id)
    if not current_user().has_role(*EXCEPTION_DECIDERS, branch_id=branch_id):
        raise Forbidden("Only the Founder / CEO or Super Admin decides a certificate release exception")
    if exception.status != "Pending":
        raise BusinessRule(f"This exception is already {exception.status}")
    approvals.require_independent(exception.requested_by, message="An independent approver must decide: not the person who asked")
    if not note:
        raise ValidationError("Invalid request data", {"note": ["Record the basis of the decision"]})
    exception.status, exception.decided_by, exception.decided_at, exception.decision_note = decision, current_user().user_id, _now(), note
    db.session.flush()
    audit.record(f"CERTIFICATE_FINANCIAL_EXCEPTION_{decision.upper()}", "admission", exception.admission.admission_code,
                 new={"exception_id": exception.exception_id, "outstanding_amount": f"{exception.outstanding_amount:.2f}"},
                 reason=note, branch_id=branch_id)
    notify(category="Certificate", title=f"Certificate release exception {decision.lower()}: {exception.admission.admission_code}",
           body=note, link="/branch/completion", recipient_user_ids=[exception.requested_by], branch_id=branch_id,
           event_key=f"financial-exception-decided:{exception.exception_id}")
    return exception
