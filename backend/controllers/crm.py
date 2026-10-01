"""CRM event intake: envelope and per-type payload validation, then the service."""
from decimal import Decimal

from flask import request

from controllers.common import Validator, get_page_params, json_body, ok, paginated
from models.enums import (
    ADMISSION_STATUSES, COMPONENT_ROLES, COURSE_STATUSES, CRM_EVENT_STATUSES, DELIVERY_MODES, ENROLMENT_KINDS,
    PAYMENT_COMPLETIONS, SEAT_TYPES,
)
from services import crm as crm_service
from services.errors import ValidationError

EVENT_TYPES = tuple(crm_service.HANDLERS)
ID_FIELDS = ("crm_person_id", "crm_admission_id", "crm_batch_id", "complimentary_of_crm_admission_id")
LANGUAGES = ("en", "te")
INSTALLMENT_SCOPES = ("admission", "invoice")
ZERO = Decimal("0.00")

# The CRM's own column names and values (nipuna-crm db), accepted as sent and mapped to the LMS vocabulary.
# person_id / admission_id are the names docs/CRM_INTEGRATION.md documents for the CRM's IDs.
FIELD_ALIASES = {"phone": "mobile", "course_title": "title", "delivery_mode": "mode",
                 "person_id": "crm_person_id", "admission_id": "crm_admission_id",
                 "complimentary_of_admission_id": "complimentary_of_crm_admission_id"}
# Top-level names of one event type only. A CRM branch's receipt_prefix (e.g. 'GNT') is the short code the LMS puts
# inside batch codes, and its email is the branch's shared mailbox (a person's email stays `email`).
EVENT_ALIASES = {"BranchUpserted": {"receipt_prefix": "short_code", "email": "mailbox"}}
VALUE_MAPS = {
    "mode": {"Online": "Live Online"},                                   # CRM delivery_mode
    "preferred_language": {"English": "en", "Telugu": "te"},             # CRM app_language
}


def _from_crm(value):
    """Numeric CRM IDs become text; CRM field names and values become the LMS's (e.g. mode 'Online' → 'Live Online')."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            alias = FIELD_ALIASES.get(key)
            if alias and alias not in value:  # an LMS-named field sent alongside wins
                key = alias
            if key in ID_FIELDS and isinstance(item, int) and not isinstance(item, bool):
                item = str(item)
            elif key in VALUE_MAPS and isinstance(item, str):
                item = VALUE_MAPS[key].get(item, item)
            out[key] = _from_crm(item)
        return out
    if isinstance(value, list):
        return [_from_crm(v) for v in value]
    return value


# ---------------------------------------------------------------- payloads per event type

def _course_upserted(v: Validator) -> None:
    v.string("course_code", required=True, upper=True, max_length=30)
    v.string("title", required=True, max_length=255)  # CRM courses.course_title is varchar(255)
    v.string("category", nullable=True, max_length=100)
    v.boolean("is_combo", default=False)
    v.choice("status", COURSE_STATUSES, default="Active")

    def component(c: Validator) -> None:
        # The CRM's combo_courses rows carry only the component course (+ is_bonus); track code / name are derived
        has_course = bool(c.data.get("component_course_code"))
        c.string("component_course_code", upper=True, max_length=30)
        c.string("track_code", required=not has_course, upper=True, max_length=50)
        c.string("track_name", required=not has_course, max_length=255)
        c.boolean("is_bonus", default=False)
        c.choice("role", COMPONENT_ROLES)
        c.integer("sort_order", default=0, min_value=0)

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
        p.string("person_code", nullable=True, max_length=30)
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
        a.choice("seat_type", SEAT_TYPES, nullable=True)
        a.date("planned_start_date", nullable=True)
        a.string("complimentary_of_crm_admission_id", nullable=True, max_length=100)
        a.date("access_until", nullable=True)          # complimentary access period (CRM admissions.access_until)
        a.string("crm_batch_id", nullable=True, max_length=100)

    v.nested("person", person, required=True)
    v.nested("admission", admission, required=True)
    # A CRM admission is one course: without enrolments the LMS enrols the admission's own course
    v.list_of("enrolments", _enrolment_item, min_items=1)


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
    v.string("reason", nullable=True)  # the CRM's free-text cancellation reason has no length limit


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
    def installment(i: Validator) -> None:
        i.integer("installment_no", required=True, min_value=1)
        i.date("due_date", required=True)
        i.decimal("amount", required=True, min_value=0)
        i.decimal("covered", default=ZERO, min_value=0)
        i.decimal("balance", default=ZERO, min_value=0)
        i.string("due_position", nullable=True, max_length=30)

    v.list_of("receipts", receipt)
    v.decimal("pending_verification", default=ZERO, min_value=0)
    v.decimal("waived", default=ZERO, min_value=0)
    v.decimal("refunded", default=ZERO, min_value=0)
    v.choice("payment_completion", PAYMENT_COMPLETIONS, nullable=True)
    v.string_list("invoice_numbers")
    v.list_of("installments", installment)
    v.choice("installments_scope", INSTALLMENT_SCOPES, default="admission")  # 'invoice': the invoice's schedule
    v.integer("invoice_course_count", default=1, min_value=0)
    v.datetime("as_of")


def _branch_upserted(v: Validator) -> None:
    # short_code and mailbox are needed to create a branch; the service says so when they are missing
    v.string("branch_code", required=True, upper=True, max_length=20)
    v.string("branch_name", required=True, max_length=100)
    v.string("city", required=True, max_length=100)
    v.string("short_code", upper=True, max_length=10)
    v.email("mailbox", nullable=True)
    v.boolean("is_active", default=True)


def _branch_finance_snapshot(v: Validator) -> None:
    def period(p: Validator) -> None:
        p.string("label", required=True, max_length=50)
        p.date("start", required=True)
        p.date("end", required=True)

    def collections(c: Validator) -> None:
        c.decimal("verified", required=True, min_value=0)
        c.decimal("target", nullable=True, min_value=0)

    def paid_admissions(a: Validator) -> None:
        a.integer("count", required=True, min_value=0)
        a.integer("target", nullable=True, min_value=0)

    def age_band(b: Validator) -> None:
        b.string("band", required=True, max_length=30)
        b.decimal("amount", required=True, min_value=0)
        b.integer("count", required=True, min_value=0)

    def overdue(o: Validator) -> None:
        o.decimal("amount", required=True, min_value=0)
        o.integer("count", required=True, min_value=0)
        o.list_of("by_age_band", age_band)

    def verifications(r: Validator) -> None:
        r.integer("pending_count", required=True, min_value=0)
        r.decimal("pending_amount", required=True, min_value=0)
        r.integer("overdue_count", required=True, min_value=0)
        r.datetime("oldest_at", nullable=True)

    def followups(f: Validator) -> None:
        f.integer("overdue_count", required=True, min_value=0)
        f.integer("broken_promises", required=True, min_value=0)

    v.string("branch_code", required=True, upper=True, max_length=20)
    v.datetime("as_of", required=True)
    v.nested("period", period, nullable=True)        # null: the branch has no approved target for now
    v.nested("collections", collections, required=True)
    v.nested("paid_admissions", paid_admissions, required=True)
    v.nested("overdue", overdue, required=True)
    v.nested("verifications", verifications, required=True)
    v.nested("followups", followups, required=True)


PAYLOAD_RULES = {
    "CourseUpserted": _course_upserted,
    "AdmissionQualified": _admission_qualified,
    "AdmissionUpdated": _admission_updated,
    "AdmissionCancelled": _admission_cancelled,
    "FinanceSummaryUpdated": _finance_summary_updated,
    "BranchUpserted": _branch_upserted,
    "BranchFinanceSnapshot": _branch_finance_snapshot,
}
# Lists that may be left out of a payload
OPTIONAL_LISTS = {"CourseUpserted": ("components",), "AdmissionUpdated": ("enrolments",),
                  "FinanceSummaryUpdated": ("receipts", "invoice_numbers", "installments")}


def _event_aliases(event_type: str, raw_data):
    aliases = EVENT_ALIASES.get(event_type)
    if not aliases or not isinstance(raw_data, dict):
        return raw_data
    return {(aliases[k] if k in aliases and aliases[k] not in raw_data else k): item for k, item in raw_data.items()}


def parse_data(event_type: str, raw_data) -> dict:
    v = Validator(_from_crm(_event_aliases(event_type, raw_data)))
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
