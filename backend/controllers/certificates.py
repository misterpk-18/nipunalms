from flask import Response, request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated
from models import Certificate
from models.attendance_enums import CERTIFICATE_STATUSES, CERTIFICATE_TYPES
from models.certificates import APPROVAL_STATUSES, REQUEST_KINDS
from repositories import certificates as certificates_repo
from services import certificate_requests as requests_service
from services import certificates as certificates_service
from services import student_certificates


def _entry(certificate: Certificate, actions: list[str]) -> dict:
    """A register row with its fee clearance and any request waiting for a decision."""
    pending = certificates_repo.pending_request(certificate.certificate_id)
    return {**certificate.to_dict(actions), "fee_clearance": certificates_service.fee_clearance(certificate),
            "pending_request": None if pending is None else {"request_id": pending.request_id, "kind": pending.kind}}


def list_register():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    v.integer("course_id", min_value=1)
    v.choice("status", CERTIFICATE_STATUSES)
    v.choice("certificate_type", CERTIFICATE_TYPES)
    v.string("q", max_length=100)
    filters = v.validate()
    page, per_page = get_page_params()
    rows, meta = certificates_service.list_register(filters, page, per_page)
    return paginated([_entry(c, actions) for c, actions in rows], meta)


def my_certificates():
    result = student_certificates.get_overview()
    return ok({"certificates": [c.to_dict() for c in result["certificates"]], "configuration_pending": result["configuration_pending"],
               "cards": result["cards"]})


def my_certificate_pdf(certificate_id: int):
    content, filename = student_certificates.certificate_pdf(certificate_id)
    return Response(content, mimetype="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"',
                                                                  "Cache-Control": "private, no-store"})


def get_certificate(certificate_id: int):
    certificate, history, actions = certificates_service.get_certificate(certificate_id)
    return ok({**_entry(certificate, actions), "history": [_history_item(c) for c in history],
               "status_history": [h.to_dict() for h in certificates_repo.status_history(certificate.certificate_id)]})


def _history_item(certificate: Certificate) -> dict:
    return {"certificate_id": certificate.certificate_id, "version": certificate.version, "status": certificate.status,
            "holder_name": certificate.holder_name, "issue_date": certificate.issue_date, "reason": certificate.reason}


def create_entry():
    v = Validator(json_body())
    v.integer("enrolment_id", required=True, min_value=1)
    v.choice("certificate_type", CERTIFICATE_TYPES, required=True)
    data = v.validate()
    return created(certificates_service.create_entry(data["enrolment_id"], data["certificate_type"]).to_dict())


def recommend(certificate_id: int):
    v = Validator(json_body())
    v.string("note", nullable=True, max_length=1000)
    return ok(_with_actions(certificates_service.recommend(certificate_id, v.validate().get("note"))))


def return_to_review(certificate_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, max_length=1000)
    return ok(_with_actions(certificates_service.return_to_review(certificate_id, v.validate()["reason"])))


def approve(certificate_id: int):
    return ok(_with_actions(certificates_service.approve(certificate_id)))


def issue(certificate_id: int):
    return ok(_with_actions(certificates_service.issue(certificate_id)))


def request_change(certificate_id: int):
    v = Validator(json_body())
    v.choice("kind", REQUEST_KINDS, required=True)
    v.string("reason", required=True, max_length=1000)
    v.string("evidence", nullable=True, max_length=2000)
    v.string("holder_name", nullable=True, max_length=150)
    data = v.validate()
    change = requests_service.request_change(certificate_id, data["kind"], data["reason"], data.get("evidence"), data.get("holder_name"))
    return created(change.to_dict(requests_service.actions_for_request(change)))


def list_requests():
    v = Validator(request.args.to_dict())
    v.choice("status", APPROVAL_STATUSES)
    v.choice("kind", REQUEST_KINDS)
    page, per_page = get_page_params()
    rows, meta = requests_service.list_requests(v.validate(), page, per_page)
    return paginated([r.to_dict(actions) for r, actions in rows], meta)


def _decision() -> dict:
    v = Validator(json_body())
    v.choice("decision", ("Approved", "Rejected"), required=True)
    v.string("note", nullable=True, max_length=1000)
    return v.validate()


def decide_request(request_id: int):
    data = _decision()
    decided = requests_service.decide_request(request_id, data["decision"], data.get("note"))
    return ok(decided.to_dict(requests_service.actions_for_request(decided)))


def request_exception(certificate_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, max_length=1000)
    exception = requests_service.request_exception(certificate_id, v.validate()["reason"])
    return created({**exception.to_dict(), "actions": requests_service.actions_for_exception(exception)})


def list_exceptions():
    v = Validator(request.args.to_dict())
    v.choice("status", APPROVAL_STATUSES)
    page, per_page = get_page_params()
    rows, meta = requests_service.list_exceptions(v.validate(), page, per_page)
    return paginated([{**e.to_dict(), "actions": actions} for e, actions in rows], meta)


def decide_exception(exception_id: int):
    data = _decision()
    decided = requests_service.decide_exception(exception_id, data["decision"], data.get("note"))
    return ok({**decided.to_dict(), "actions": requests_service.actions_for_exception(decided)})


def verify(number: str):
    """Public: the presented version's state, holder, course, type, branch and dates only. `?version=` checks an older copy."""
    v = Validator(request.args.to_dict())
    v.integer("version", min_value=1)
    return ok(certificates_service.verify(number, v.validate().get("version")))


def _with_actions(certificate: Certificate) -> dict:
    return _entry(certificate, certificates_service.actions_for(certificate))
