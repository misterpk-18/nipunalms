from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated
from models import Certificate
from models.attendance_enums import CERTIFICATE_STATUSES, CERTIFICATE_TYPES
from services import certificates as certificates_service


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
    return paginated([c.to_dict(actions) for c, actions in rows], meta)


def my_certificates():
    result = certificates_service.my_certificates()
    return ok({"certificates": [c.to_dict() for c in result["certificates"]], "configuration_pending": result["configuration_pending"]})


def get_certificate(certificate_id: int):
    certificate, history, actions = certificates_service.get_certificate(certificate_id)
    return ok({**certificate.to_dict(actions), "history": [_history_item(c) for c in history]})


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


def reissue(certificate_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, max_length=1000)
    v.string("holder_name", nullable=True, max_length=150)
    data = v.validate()
    return created(_with_actions(certificates_service.reissue(certificate_id, data["reason"], data.get("holder_name"))))


def revoke(certificate_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, max_length=1000)
    return ok(_with_actions(certificates_service.revoke(certificate_id, v.validate()["reason"])))


def verify(number: str):
    """Public: holder, course, issue date and status only."""
    certificate = certificates_service.verify(number)
    return ok({
        "certificate_number": certificate.certificate_number,
        "holder_name": certificate.holder_name,
        "course": {"course_code": certificate.course.course_code, "title": certificate.course.title},
        "certificate_type": certificate.certificate_type,
        "issue_date": certificate.issue_date,
        "status": certificate.status,
        "version": certificate.version,
    })


def _with_actions(certificate: Certificate) -> dict:
    return certificate.to_dict(certificates_service.actions_for(certificate))
