"""CRM event intake: envelope and per-type payload validation, then the service."""
from flask import request

from controllers.common import Validator, get_page_params, json_body, ok, paginated
from models.enums import ADMISSION_STATUSES, CRM_EVENT_STATUSES, COURSE_STATUSES, COMPONENT_ROLES, DELIVERY_MODES, ENROLMENT_KINDS
from services import crm as crm_service
from services.errors import ValidationError

EVENT_TYPES = tuple(crm_service.HANDLERS)
ID_FIELDS = ("crm_person_id", "crm_admission_id", "crm_batch_id")
LANGUAGES = ("en", "te")


def _stringify_ids(value):
    """The CRM may send numeric IDs; the LMS stores them as text."""
    if isinstance(value, dict):
        return {k: str(v) if k in ID_FIELDS and isinstance(v, int) and not isinstance(v, bool) else _stringify_ids(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [_stringify_ids(v) for v in value]
    return value


# ---------------------------------------------------------------- payloads per event type

def _course_upserted(v: Validator) -> None:
    v.string("course_code", required=True, upper=True, max_length=30)
    v.string("title", required=True, max_length=200)
    v.string("category", nullable=True, max_length=100)
    v.boolean("is_combo", default=False)
    v.choice("status", COURSE_STATUSES, default="Active")

    def component(c: Validator) -> None:
        c.string("track_code", required=True, upper=True, max_length=50)
        c.string("track_name", required=True, max_length=200)
        c.choice("role", COMPONENT_ROLES, default="Main track")
        c.integer("sort_order", default=0, min_value=0)
        c.string("component_course_code", upper=True, max_length=30)

    v.list_of("components", component)


def _enrolment_item(e: Validator) -> None:
    complimentary = e.data.get("kind") == "Complimentary"
    e.string("course_code", required=True, upper=True, max_length=30)
    e.choice("kind", ENROLMENT_KINDS)
    e.choice("mode", DELIVERY_MODES)
    e.string_list("tracks")
    e.string("parent_course_code", required=complimentary, upper=True, max_length=30)
    e.nested("benefit_gate", _benefit_gate, required=complimentary)
    e.string("crm_batch_id", max_length=100)
    e.date("access_start")
    e.date("access_end")


def _benefit_gate(g: Validator) -> None:
    g.boolean("met", required=True)
    g.string("note", nullable=True, max_length=500)


def _admission_qualified(v: Validator) -> None:
    def person(p: Validator) -> None:
        p.string("crm_person_id", required=True, max_length=100)
        p.string("full_name", required=True, max_length=150)
        p.string("name_te", nullable=True, max_length=200)
        p.email("email", nullable=True)
        p.phone("mobile", nullable=True)
        p.choice("preferred_language", LANGUAGES)

    def admission(a: Validator) -> None:
        a.string("crm_admission_id", required=True, max_length=100)
        a.string("admission_code", required=True, max_length=50)
        a.string("course_code", required=True, upper=True, max_length=30)
        a.string("original_branch_code", required=True, upper=True, max_length=20)
        a.string("service_branch_code", required=True, upper=True, max_length=20)
        a.string("collecting_branch_code", required=True, upper=True, max_length=20)
        a.choice("mode", DELIVERY_MODES, default="Classroom")
        a.date("admission_date", nullable=True)

    v.nested("person", person, required=True)
    v.nested("admission", admission, required=True)
    v.list_of("enrolments", _enrolment_item, required=True, min_items=1)


def _admission_updated(v: Validator) -> None:
    def enrolment(e: Validator) -> None:
        e.string("course_code", required=True, upper=True, max_length=30)
        e.string("crm_batch_id", required=True, max_length=100)

    v.string("crm_admission_id", required=True, max_length=100)
    v.string("service_branch_code", upper=True, max_length=20)
    v.choice("mode", DELIVERY_MODES)
    v.choice("status", tuple(s for s in ADMISSION_STATUSES if s != "Cancelled"))
    v.list_of("enrolments", enrolment)


def _admission_cancelled(v: Validator) -> None:
    v.string("crm_admission_id", required=True, max_length=100)
    v.string("reason", nullable=True, max_length=500)


def _finance_summary_updated(v: Validator) -> None:
    def receipt(r: Validator) -> None:
        r.string("receipt_number", required=True, max_length=50)
        r.date("date", required=True)
        r.decimal("amount", required=True, min_value=0)

    v.string("crm_admission_id", required=True, max_length=100)
    v.decimal("fee_total", required=True, min_value=0)
    v.decimal("verified_paid", required=True, min_value=0)
    v.decimal("balance", required=True)
    v.date("next_due_date", nullable=True)
    v.decimal("next_due_amount", nullable=True, min_value=0)
    v.list_of("receipts", receipt)
    v.datetime("as_of")


PAYLOAD_RULES = {
    "CourseUpserted": _course_upserted,
    "AdmissionQualified": _admission_qualified,
    "AdmissionUpdated": _admission_updated,
    "AdmissionCancelled": _admission_cancelled,
    "FinanceSummaryUpdated": _finance_summary_updated,
}
# Lists that may be left out of a payload
OPTIONAL_LISTS = {"CourseUpserted": ("components",), "AdmissionUpdated": ("enrolments",),
                  "FinanceSummaryUpdated": ("receipts",)}


def parse_data(event_type: str, raw_data) -> dict:
    v = Validator(_stringify_ids(raw_data))
    PAYLOAD_RULES[event_type](v)
    data = v.validate()
    for field in OPTIONAL_LISTS.get(event_type, ()):
        data.setdefault(field, [])
    return data


# ---------------------------------------------------------------- endpoints

def _parse_envelope(body: dict) -> dict:
    v = Validator(body)
    v.string("event_id", required=True, max_length=100)
    v.choice("event_type", EVENT_TYPES, required=True)
    v.integer("source_version", required=True, min_value=1)
    v.datetime("occurred_at", required=True)
    v.nested("data", lambda inner: None, required=True)
    envelope = v.validate()
    envelope["data"] = body["data"]  # kept exactly as received
    return envelope


def _event_body(outcome: crm_service.Outcome) -> dict:
    return {**outcome.event.to_dict(), "result": outcome.event.result, "replayed": outcome.replayed,
            "activation_token": outcome.activation_token}


def receive_event():
    body = json_body()
    envelope = _parse_envelope(body)
    try:
        data = parse_data(envelope["event_type"], envelope["data"])
    except ValidationError as exc:
        crm_service.record_rejected(envelope, exc)
        raise
    outcome = crm_service.receive(envelope, data)
    return ok(_event_body(outcome), status=200 if outcome.replayed else 201)


def list_events():
    v = Validator(request.args.to_dict())
    v.choice("status", CRM_EVENT_STATUSES)
    v.choice("event_type", EVENT_TYPES)
    filters = v.validate()

    page, per_page = get_page_params()
    events, meta = crm_service.list_events(filters, page, per_page)
    return paginated([e.to_dict(include_payload=True) for e in events], meta)


def retry_event(crm_event_id: int):
    event = crm_service.get_event(crm_event_id)
    data = parse_data(event.event_type, event.payload)
    return ok(crm_service.retry(event, data).to_dict(include_payload=True))


def get_status():
    v = Validator({"since": request.args.get("since", "1970-01-01T00:00:00+00:00").replace(" ", "+")})
    v.datetime("since")
    return ok(crm_service.status_since(v.validate()["since"]))
