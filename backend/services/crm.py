"""CRM intake: versioned, idempotent events from the CRM (guide §17 / §17A), and the status the CRM can pull back.

Every event is stored in crm_events with its outcome. Rules:
  - the same event_id with the same payload returns the original result; with a different payload it is a 409;
  - an event older than the state it would change (source_version) is stored as 'Ignored — stale' and changes nothing;
  - an event that cannot be applied yet (e.g. its course or admission has not arrived) is stored as 'Failed' with
    the reason, and can be retried; the CRM can also simply send it again.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.exc import DBAPIError

from config.database import db
from models import (
    Admission, Course, CourseComponent, CrmEvent, Enrolment, EnrolmentTrack, FinanceSummary, Student, User,
)
from repositories import batches as batches_repo
from repositories import branches as branches_repo
from repositories import catalog as catalog_repo
from repositories import crm as crm_repo
from repositories import students as students_repo
from repositories import users as users_repo
from services import activation, allocations, audit
from repositories.common import paginate
from services.errors import AppError, BusinessRule, Conflict, NotFound, ValidationError
from services.notifications import notify

logger = logging.getLogger(__name__)

STALE = "Ignored — stale"
OPEN_STATUSES = ("Allocation Pending", "Allocated — awaiting first regular class", "Active", "Paused",
                 "Curriculum Mapping Pending", "Provisioning Pending")


@dataclass
class Handled:
    """What applying an event produced. stale=True: nothing was changed."""

    result: dict
    stale: bool = False
    activation_token: str | None = None  # raw token of a newly created LMS login; returned to the CRM once, never stored


@dataclass
class Outcome:
    event: CrmEvent
    replayed: bool
    activation_token: str | None = None


# ---------------------------------------------------------------- receiving events

def receive(envelope: dict, data: dict) -> Outcome:
    """Store and apply one event. `envelope` is the raw request (event_id, event_type, source_version,
    occurred_at, data); `data` is the validated data for the event type."""
    existing = crm_repo.get_event_by_event_id(envelope["event_id"])
    if existing is not None:
        if not _same_event(existing, envelope):
            raise Conflict("This event_id was already used with a different payload", {"event_id": [envelope["event_id"]]})
        if existing.status in ("Applied", STALE):
            return Outcome(existing, replayed=True)
        return _process(existing, data, replayed=True)  # a failed event sent again is retried

    event = CrmEvent(event_id=envelope["event_id"], event_type=envelope["event_type"],
                     source_version=envelope["source_version"], occurred_at=envelope["occurred_at"],
                     payload=envelope["data"])
    db.session.add(event)
    db.session.flush()
    return _process(event, data, replayed=False)


def record_rejected(envelope: dict, error: ValidationError) -> None:
    """The event's data failed validation: keep it in the inbox as Failed (so it is visible), then let the 400 through."""
    if crm_repo.get_event_by_event_id(envelope["event_id"]) is None:
        db.session.add(CrmEvent(event_id=envelope["event_id"], event_type=envelope["event_type"],
                                source_version=envelope["source_version"], occurred_at=envelope["occurred_at"],
                                payload=envelope["data"], status="Failed",
                                error=f"{error.message}: {error.details}", processed_at=datetime.now(timezone.utc)))
        db.session.commit()  # the 400 response would roll this back


def get_event(crm_event_id: int) -> CrmEvent:
    event = crm_repo.get_event(crm_event_id)
    if event is None:
        raise NotFound("CRM event not found")
    return event


def list_events(filters: dict, page: int, per_page: int):
    return paginate(crm_repo.events_stmt(filters), page, per_page)


def retry(event: CrmEvent, data: dict) -> CrmEvent:
    """Super Admin: apply a failed event again."""
    if event.status not in ("Failed", "Received"):
        raise BusinessRule(f"Only failed events can be retried; this one is '{event.status}'")
    return _process(event, data, replayed=True).event


def _same_event(event: CrmEvent, envelope: dict) -> bool:
    return (event.event_type == envelope["event_type"] and event.source_version == envelope["source_version"]
            and event.occurred_at == envelope["occurred_at"] and event.payload == envelope["data"])


def _process(event: CrmEvent, data: dict, *, replayed: bool) -> Outcome:
    if replayed:
        event.retries += 1
    try:
        with db.session.begin_nested():  # a failed apply leaves no partial changes behind
            handled = HANDLERS[event.event_type](event, data)
    except Exception as exc:
        event.status = "Failed"
        event.error = _error_text(exc)
        event.processed_at = datetime.now(timezone.utc)
        db.session.commit()  # the error response would roll the failure record back
        logger.warning("CRM event %s (%s) failed: %s", event.event_id, event.event_type, event.error)
        raise
    event.status = STALE if handled.stale else "Applied"
    event.result = handled.result
    event.error = None
    event.processed_at = datetime.now(timezone.utc)
    db.session.flush()
    return Outcome(event, replayed=replayed, activation_token=handled.activation_token)


def _error_text(exc: Exception) -> str:
    if isinstance(exc, AppError):
        return exc.message
    if isinstance(exc, DBAPIError):
        diag = getattr(exc.orig, "diag", None)
        return (diag.message_primary if diag else None) or str(exc.orig)
    return f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------- lookups shared by the handlers

def _branch(code: str):
    branch = branches_repo.get_by_code(code)
    if branch is None:
        raise BusinessRule(f"Unknown branch '{code}'")
    return branch


def _course(course_code: str) -> Course:
    course = catalog_repo.get_course_by_code(course_code)
    if course is None:
        raise BusinessRule(f"Unknown course '{course_code}': its CourseUpserted event has not been applied yet")
    return course


def _admission(crm_admission_id: str) -> Admission:
    admission = students_repo.get_admission_by_crm_id(crm_admission_id)
    if admission is None:
        raise BusinessRule(f"Unknown admission '{crm_admission_id}': its AdmissionQualified event has not been applied yet")
    return admission


def _stale(event: CrmEvent, stored_version: int, what: str) -> Handled:
    return Handled({"reason": f"{what} is already at source_version {stored_version}; this event is {event.source_version}"},
                   stale=True)


# ---------------------------------------------------------------- CourseUpserted

def _course_upserted(event: CrmEvent, data: dict) -> Handled:
    course = catalog_repo.get_course_by_code(data["course_code"])
    if course is not None and event.source_version < course.source_version:
        return _stale(event, course.source_version, f"Course {course.course_code}")
    if course is None:
        course = Course(course_code=data["course_code"])
        db.session.add(course)

    course.title = data["title"]
    course.category = data.get("category")
    course.is_combo = data["is_combo"]
    course.status = data["status"]
    course.source_version = event.source_version
    db.session.flush()

    for item in data["components"]:
        component_course = _course(item["component_course_code"]) if item.get("component_course_code") else None
        component = catalog_repo.get_component_by_track_code(item["track_code"])
        if component is not None and component.parent_course_id != course.course_id:
            raise BusinessRule(f"Track {item['track_code']} already belongs to another course")
        if component is None:
            component = CourseComponent(parent_course_id=course.course_id, track_code=item["track_code"])
            db.session.add(component)
        component.track_name = item["track_name"]
        component.role = item["role"]
        component.sort_order = item["sort_order"]
        component.component_course_id = component_course.course_id if component_course else None
    db.session.flush()
    return Handled({"course_id": course.course_id, "course_code": course.course_code,
                    "components": len(data["components"])})


# ---------------------------------------------------------------- AdmissionQualified

def _admission_qualified(event: CrmEvent, data: dict) -> Handled:
    person, adm = data["person"], data["admission"]
    admission = students_repo.get_admission_by_crm_id(adm["crm_admission_id"])
    if admission is not None and event.source_version < admission.source_version:
        return _stale(event, admission.source_version, f"Admission {admission.admission_code}")

    original, service, collecting = (_branch(adm["original_branch_code"]), _branch(adm["service_branch_code"]),
                                     _branch(adm["collecting_branch_code"]))
    course = _course(adm["course_code"])

    student, token, warnings = _upsert_student(person, original.branch_id, service.branch_id)

    if admission is None:
        admission = Admission(crm_admission_id=adm["crm_admission_id"], student_id=student.student_id)
        db.session.add(admission)
    elif admission.student_id != student.student_id:
        raise BusinessRule(f"Admission {admission.admission_code} belongs to a different person")
    admission.admission_code = adm["admission_code"]
    admission.course_id = course.course_id
    admission.original_branch_id = original.branch_id
    admission.service_branch_id = service.branch_id
    admission.collecting_branch_id = collecting.branch_id
    admission.mode = adm["mode"]
    admission.admission_date = adm.get("admission_date")
    admission.source_version = event.source_version
    db.session.flush()

    # Paid enrolments first: a complimentary one links to its qualifying paid enrolment
    items = sorted(data["enrolments"], key=lambda i: i.get("kind") == "Complimentary")
    enrolments = [_ensure_enrolment(admission, student, item, warnings) for item in items]

    pending = [f"{e.enrolment_code} {e.status}" for e in enrolments if e.status.endswith("Pending")]
    notify(category="Enrolment", event_key=f"admission-qualified:{admission.crm_admission_id}",
           title=f"New admission: {student.full_name} — {course.title}",
           body="; ".join(pending) if pending else "All enrolments are ready for allocation.",
           link=f"/academic/students/{student.student_id}", role_code="ACADEMIC_COORDINATOR",
           branch_id=service.branch_id, action_required=bool(pending))
    db.session.flush()

    return Handled({**_admission_result(admission, student), "activation_status": student.activation_status,
                    "enrolments": [_enrolment_result(e) for e in enrolments], "warnings": warnings},
                   activation_token=token)


def _upsert_student(person: dict, original_branch_id: int, service_branch_id: int) -> tuple[Student, str | None, list[str]]:
    """One student per CRM Person; the LMS login is created the first time only. Returns the raw activation token of a new login."""
    warnings: list[str] = []
    student = students_repo.get_student_by_crm_person_id(person["crm_person_id"])
    if student is None:
        student = Student(crm_person_id=person["crm_person_id"], full_name=person["full_name"],
                          original_branch_id=original_branch_id, service_branch_id=service_branch_id)
        db.session.add(student)
    for field in ("full_name", "name_te", "email", "mobile", "preferred_language"):
        if person.get(field) is not None:
            setattr(student, field, person[field])
    db.session.flush()

    token = None
    if users_repo.get_by_student_id(student.student_id) is None:
        email = student.email
        if email and users_repo.email_taken(email):
            warnings.append("The student's email is already used by another login; they sign in with their Student ID")
            email = None
        db.session.add(User(full_name=student.full_name, email=email, student_id=student.student_id))
        db.session.flush()
        student.provisioned_at = datetime.now(timezone.utc)
        token = activation.issue(student, channel="CRM provisioning", issued_by=None).token
    return student, token, warnings


def _ensure_enrolment(admission: Admission, student: Student, item: dict, warnings: list[str]) -> Enrolment:
    course = _course(item["course_code"])
    kind = item.get("kind") or ("Combo" if course.is_combo else "Standalone")
    gate = item.get("benefit_gate")

    enrolment = students_repo.find_enrolment(admission.admission_id, course.course_id)
    if enrolment is None:
        enrolment = Enrolment(admission_id=admission.admission_id, student_id=student.student_id,
                              course_id=course.course_id, kind=kind, service_branch_id=admission.service_branch_id,
                              mode=item.get("mode") or admission.mode,
                              status="Provisioning Pending" if gate and not gate["met"] else "Curriculum Mapping Pending")
        if kind == "Complimentary":
            parent_course = _course(item["parent_course_code"])
            parent = students_repo.find_enrolment(admission.admission_id, parent_course.course_id)
            if parent is None:
                raise BusinessRule(f"Complimentary course {course.course_code} needs its qualifying enrolment "
                                   f"{parent_course.course_code} in the same admission")
            enrolment.parent_enrolment_id = parent.enrolment_id
        db.session.add(enrolment)
    elif enrolment.status not in ("Curriculum Mapping Pending", "Provisioning Pending"):
        _link_batch(enrolment, item, warnings)
        return enrolment  # already being served: a repeated qualification never resets its progress

    enrolment.access_start = item.get("access_start", enrolment.access_start)
    enrolment.access_end = item.get("access_end", enrolment.access_end)
    if gate is not None:
        enrolment.benefit_gate_met = gate["met"]
        enrolment.benefit_note = gate.get("note")
    db.session.flush()

    _map_curriculum(enrolment, course, item.get("tracks"))
    _link_batch(enrolment, item, warnings)
    return enrolment


def _map_curriculum(enrolment: Enrolment, course: Course, track_codes: list[str] | None) -> None:
    """Attach the Active curriculum versions; without them the enrolment waits in Curriculum Mapping Pending
    (never a guessed version)."""
    enrolment.curriculum_version_id = catalog_repo.active_curriculum_version_id(course.course_id)

    if enrolment.kind == "Combo":
        components = [c for c in course.components if track_codes is None or c.track_code in track_codes]
        unknown = set(track_codes or ()) - {c.track_code for c in course.components}
        if unknown:
            raise BusinessRule(f"Unknown track(s) for {course.course_code}: {', '.join(sorted(unknown))}")
        existing = {t.component_id: t for t in enrolment.tracks}
        for component in components:
            # A version written for this track of the combo, else (for an included booster) the booster course's own
            version_id = catalog_repo.active_curriculum_version_id(course.course_id, component.component_id)
            if version_id is None and component.component_course_id:
                version_id = catalog_repo.active_curriculum_version_id(component.component_course_id)
            track = existing.get(component.component_id)
            if track is None:
                enrolment.tracks.append(EnrolmentTrack(component_id=component.component_id, curriculum_version_id=version_id))
            else:
                track.curriculum_version_id = version_id
        db.session.flush()

    gate_blocked = enrolment.benefit_gate_met is False
    unmapped = enrolment.curriculum_version_id is None or any(t.curriculum_version_id is None for t in enrolment.tracks)
    if gate_blocked:
        enrolment.status = "Provisioning Pending"
    elif unmapped:
        enrolment.status = "Curriculum Mapping Pending"
    elif batches_repo.active_allocation(enrolment.enrolment_id) is not None:
        enrolment.status = "Allocated — awaiting first regular class"  # a seat was reserved while mapping was pending
    else:
        enrolment.status = "Allocation Pending"
    db.session.flush()


def _link_batch(enrolment: Enrolment, item: dict, warnings: list[str]) -> None:
    """The CRM already allocated a batch: mirror it when the LMS batch is linked, otherwise say so."""
    crm_batch_id = item.get("crm_batch_id")
    if not crm_batch_id:
        return
    batch = batches_repo.get_batch_by_crm_id(crm_batch_id)
    if batch is None:
        warnings.append(f"CRM batch {crm_batch_id} is not linked to an LMS batch yet; {enrolment.enrolment_code} stays unallocated")
        return
    try:
        allocations.allocate(enrolment, batch, reason="Allocated by the CRM")
    except BusinessRule as exc:
        warnings.append(exc.message)


def _admission_result(admission: Admission, student: Student) -> dict:
    return {
        "admission_id": admission.admission_id,
        "crm_admission_id": admission.crm_admission_id,
        "student_id": student.student_id,
        "student_code": student.student_code,
        "lms_user_id": student.lms_user_id,
        "lms_status": students_repo.lms_status_of(admission.admission_id),
    }


def _enrolment_result(enrolment: Enrolment) -> dict:
    return {"enrolment_id": enrolment.enrolment_id, "enrolment_code": enrolment.enrolment_code,
            "course_code": enrolment.course.course_code, "kind": enrolment.kind, "status": enrolment.status}


# ---------------------------------------------------------------- AdmissionUpdated

def _resumed_status(enrolment: Enrolment) -> str:
    """Where a paused enrolment picks up again."""
    if enrolment.joining_date is not None:
        return "Active"
    if batches_repo.active_allocation(enrolment.enrolment_id) is not None:
        return "Allocated — awaiting first regular class"
    if enrolment.curriculum_version_id is not None and all(t.curriculum_version_id for t in enrolment.tracks):
        return "Allocation Pending"
    return "Curriculum Mapping Pending"


def _admission_updated(event: CrmEvent, data: dict) -> Handled:
    admission = _admission(data["crm_admission_id"])
    if event.source_version < admission.source_version:
        return _stale(event, admission.source_version, f"Admission {admission.admission_code}")
    if admission.crm_status == "Cancelled":
        raise BusinessRule(f"Admission {admission.admission_code} is cancelled and cannot be updated")

    student = students_repo.get_student(admission.student_id)
    enrolments = [e for e in students_repo.enrolments_of_admission(admission.admission_id) if e.status != "Withdrawn"]
    changes: list[str] = []
    warnings: list[str] = []

    if "service_branch_code" in data:
        new_branch = _branch(data["service_branch_code"])
        if new_branch.branch_id != admission.service_branch_id:
            _transfer(admission, student, enrolments, new_branch)
            changes.append("service branch transferred")

    if "mode" in data and data["mode"] != admission.mode:
        admission.mode = data["mode"]
        for enrolment in enrolments:
            enrolment.mode = data["mode"]
        changes.append("mode updated")

    if data.get("status") == "Paused" and admission.crm_status == "Active":
        admission.crm_status = "Paused"
        for enrolment in enrolments:
            if enrolment.status in OPEN_STATUSES and enrolment.status != "Paused":
                enrolment.status = "Paused"
        changes.append("paused")
    elif data.get("status") == "Active" and admission.crm_status == "Paused":
        admission.crm_status = "Active"
        for enrolment in enrolments:
            if enrolment.status == "Paused":
                enrolment.status = _resumed_status(enrolment)
        changes.append("resumed")

    for item in data.get("enrolments", []):
        enrolment = students_repo.find_enrolment(admission.admission_id, _course(item["course_code"]).course_id)
        if enrolment is None:
            raise BusinessRule(f"Admission {admission.admission_code} has no enrolment for {item['course_code']}")
        _link_batch(enrolment, item, warnings)

    admission.source_version = event.source_version
    db.session.flush()
    return Handled({**_admission_result(admission, student), "changes": changes, "warnings": warnings})


def _transfer(admission: Admission, student: Student, enrolments: list[Enrolment], new_branch) -> None:
    """Service branch transfer: seats at the old branch are released, the new branch's coordinator is asked to re-allocate."""
    old_branch_id = admission.service_branch_id
    admission.service_branch_id = new_branch.branch_id
    for enrolment in enrolments:
        allocations.end(enrolment, "Transferred", reason=f"Service branch transferred to {new_branch.branch_code}")
        enrolment.service_branch_id = new_branch.branch_id
    audit.record("ADMISSION_TRANSFERRED", "admission", admission.admission_code, branch_id=new_branch.branch_id,
                 old={"service_branch_id": old_branch_id}, new={"service_branch_id": new_branch.branch_id})
    notify(category="Enrolment", event_key=f"admission-transfer:{admission.crm_admission_id}:{admission.source_version}:{new_branch.branch_id}",
           title=f"Transferred in: {student.full_name} ({admission.admission_code})",
           body="Allocate the student to a batch at this branch.", link=f"/academic/students/{student.student_id}",
           role_code="ACADEMIC_COORDINATOR", branch_id=new_branch.branch_id, action_required=True)


# ---------------------------------------------------------------- AdmissionCancelled

def _admission_cancelled(event: CrmEvent, data: dict) -> Handled:
    admission = _admission(data["crm_admission_id"])
    if event.source_version < admission.source_version:
        return _stale(event, admission.source_version, f"Admission {admission.admission_code}")

    student = students_repo.get_student(admission.student_id)
    withdrawn = 0
    for enrolment in students_repo.enrolments_of_admission(admission.admission_id):
        if enrolment.status not in ("Withdrawn", "Completed"):
            allocations.end(enrolment, reason="Admission cancelled")
            enrolment.status = "Withdrawn"
            withdrawn += 1
    if admission.crm_status != "Cancelled":
        audit.record("ADMISSION_CANCELLED", "admission", admission.admission_code, branch_id=admission.service_branch_id,
                     old={"crm_status": admission.crm_status}, new={"crm_status": "Cancelled"}, reason=data.get("reason"))
    admission.crm_status = "Cancelled"
    admission.source_version = event.source_version
    db.session.flush()
    return Handled({**_admission_result(admission, student), "enrolments_withdrawn": withdrawn})


# ---------------------------------------------------------------- FinanceSummaryUpdated

def _finance_summary_updated(event: CrmEvent, data: dict) -> Handled:
    admission = _admission(data["crm_admission_id"])
    summary = students_repo.get_finance_summary(admission.admission_id)
    if summary is not None and event.source_version < summary.source_version:
        return _stale(event, summary.source_version, f"The finance summary of {admission.admission_code}")
    if summary is None:
        summary = FinanceSummary(admission_id=admission.admission_id)
        db.session.add(summary)

    summary.fee_total = data["fee_total"]
    summary.verified_paid = data["verified_paid"]
    summary.balance = data["balance"]
    summary.next_due_date = data.get("next_due_date")
    summary.next_due_amount = data.get("next_due_amount")
    summary.receipts = [{"receipt_number": r["receipt_number"], "date": r["date"].isoformat(), "amount": str(r["amount"])}
                        for r in data["receipts"]]
    summary.as_of = data.get("as_of") or event.occurred_at
    summary.source_version = event.source_version
    db.session.flush()
    return Handled({"admission_id": admission.admission_id, "crm_admission_id": admission.crm_admission_id,
                    "balance": str(summary.balance)})


HANDLERS: dict[str, Callable[[CrmEvent, dict], Handled]] = {
    "CourseUpserted": _course_upserted,
    "AdmissionQualified": _admission_qualified,
    "AdmissionUpdated": _admission_updated,
    "AdmissionCancelled": _admission_cancelled,
    "FinanceSummaryUpdated": _finance_summary_updated,
}


# ---------------------------------------------------------------- what the CRM pulls back

def status_since(since: datetime) -> dict:
    """The values the CRM stores about the LMS that changed after `since`:
    persons.lms_user_id / lms_provisioned_at, admissions.lms_status / lms_last_activity_at, batches.lms_course_id."""
    now = datetime.now(timezone.utc)
    return {
        "persons": [{"crm_person_id": s.crm_person_id, "lms_user_id": s.lms_user_id, "lms_provisioned_at": s.provisioned_at}
                    for s in crm_repo.students_provisioned_since(since)],
        "admissions": [{"crm_admission_id": st.admission.crm_admission_id, "lms_status": st.lms_status,
                        "lms_last_activity_at": st.last_activity_at, "lms_last_synced_at": now}
                       for st in crm_repo.admission_states_changed_since(since)],
        "batches": [{"crm_batch_id": b.crm_batch_id, "lms_course_id": b.batch_code}
                    for b in crm_repo.batches_linked_since(since)],
        "as_of": now,
    }
