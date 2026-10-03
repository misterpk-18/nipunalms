"""Student slot preferences (Module 15 §7, §13): a student asks for days, times, a mode or a particular batch; staff mark the
request Waitlisted, Confirmed or Not Possible. A request reserves no seat, and Confirmed is only shown once the student
actually holds a seat in that batch."""
from datetime import datetime, timezone

from sqlalchemy import select

from config.database import db
from models import Enrolment, SlotPreference
from repositories import batches as batches_repo
from repositories import students as students_repo
from repositories.common import paginate_rows
from services import audit, delivery_access, delivery_notices, scope
from services.context import actor_id
from services.errors import BusinessRule, Conflict, NotFound, ValidationError

OPEN = ("Requested", "Waitlisted")
STAFF_STATUSES = ("Waitlisted", "Confirmed", "Not Possible")
CLOSED_ENROLMENT = ("Completed", "Withdrawn")


def _own_enrolment(enrolment_id: int):
    if enrolment_id not in scope.student_enrolment_ids():
        raise NotFound("Enrolment not found")
    enrolment = students_repo.get_enrolment(enrolment_id)
    if enrolment.status in CLOSED_ENROLMENT:
        raise BusinessRule(f"The enrolment is {enrolment.status}")
    return enrolment


def options(enrolment_id: int) -> list[dict]:
    """Batches of the student's course at their service branch that still take students, labelled honestly: a Proposed
    batch is not confirmed, a full batch has no seat."""
    enrolment = _own_enrolment(enrolment_id)
    batches = batches_repo.open_batches_for(enrolment.course_id, enrolment.service_branch_id)
    counts = batches_repo.allocated_counts([b.batch_id for b in batches])
    rows = []
    for batch in batches:
        detail = batch.to_dict(allocated_count=counts.get(batch.batch_id, 0))
        rows.append({k: detail[k] for k in ("batch_id", "batch_code", "display_name", "mode", "schedule_pattern", "planned_start",
                                            "schedule_days", "start_time", "end_time", "state_label", "is_full")})
    return rows


def create(data: dict) -> SlotPreference:
    enrolment = _own_enrolment(data["enrolment_id"])
    if data.get("batch_id"):
        batch = batches_repo.get_batch(data["batch_id"])
        if batch is None or batch.batch_id not in {b.batch_id for b in batches_repo.open_batches_for(enrolment.course_id, enrolment.service_branch_id)}:
            raise ValidationError("Unknown batch", {"batch_id": ["Not an open batch of your course at your branch"]})
    if not (data.get("batch_id") or data.get("preferred_days") or data.get("preferred_start")):
        raise ValidationError("Say what you prefer", {"preferred_days": ["Give days, times or a batch"]})
    if (data.get("preferred_start") is None) != (data.get("preferred_end") is None):
        raise ValidationError("Invalid times", {"preferred_end": ["Give both the start and end time"]})
    if data.get("preferred_start") and data["preferred_end"] <= data["preferred_start"]:
        raise ValidationError("Invalid times", {"preferred_end": ["Must be after the start time"]})
    if db.session.execute(select(SlotPreference).where(SlotPreference.enrolment_id == enrolment.enrolment_id,
                                                       SlotPreference.status.in_(OPEN))).first():
        raise Conflict("You already have an open slot request for this course; withdraw it first")
    preference = SlotPreference(enrolment_id=enrolment.enrolment_id, batch_id=data.get("batch_id"),
                                preferred_days=data.get("preferred_days"), preferred_start=data.get("preferred_start"),
                                preferred_end=data.get("preferred_end"), preferred_mode=data.get("preferred_mode"), note=data.get("note"),
                                created_by=actor_id())
    db.session.add(preference)
    db.session.flush()
    delivery_notices.notify_branch_managers(enrolment.service_branch_id, title=f"Slot request: {enrolment.enrolment_code}",
                                            body=f"{enrolment.course.course_code}. A request reserves no seat.", category="Enrolment",
                                            event_key=f"slot-preference-{preference.preference_id}", link="/academic/batches")
    return preference


def mine() -> list[SlotPreference]:
    ids = scope.student_enrolment_ids()
    if not ids:
        return []
    stmt = select(SlotPreference).where(SlotPreference.enrolment_id.in_(ids)).order_by(SlotPreference.created_at.desc())
    return list(db.session.execute(stmt).scalars())


def withdraw(preference_id: int) -> SlotPreference:
    preference = db.session.get(SlotPreference, preference_id)
    if preference is None or preference.enrolment_id not in scope.student_enrolment_ids():
        raise NotFound("Slot request not found")
    if preference.status not in OPEN:
        raise BusinessRule(f"The request is already {preference.status}")
    _set(preference, "Withdrawn", None)
    return preference


def list_for_staff(filters: dict, page: int, per_page: int):
    """Requests at the user's branches (a trainer sees none)."""
    branch_ids = scope.visible_branch_ids()
    stmt = (select(SlotPreference, Enrolment).join(Enrolment, Enrolment.enrolment_id == SlotPreference.enrolment_id)
            .order_by(SlotPreference.created_at.desc()))
    if branch_ids is not None:
        stmt = stmt.where(Enrolment.service_branch_id.in_(branch_ids or {0}))
    if filters.get("status"):
        stmt = stmt.where(SlotPreference.status == filters["status"])
    if filters.get("branch_id"):
        stmt = stmt.where(Enrolment.service_branch_id == filters["branch_id"])
    return paginate_rows(stmt, page, per_page)


def set_status(preference_id: int, status: str, note: str | None, batch_id: int | None) -> SlotPreference:
    preference = db.session.get(SlotPreference, preference_id)
    enrolment = students_repo.get_enrolment(preference.enrolment_id) if preference else None
    if enrolment is None:
        raise NotFound("Slot request not found")
    scope.assert_can_view_enrolment(enrolment)
    delivery_access.assert_can_manage_branch(enrolment.service_branch_id)
    if preference.status not in OPEN:
        raise BusinessRule(f"The request is already {preference.status}")
    if status == "Confirmed":
        batch_id = batch_id or preference.batch_id
        seats = {a.batch_id for a in batches_repo.active_allocations_of(enrolment.enrolment_id)}
        if batch_id is None or batch_id not in seats:
            raise BusinessRule("Confirm a slot only once the student holds a seat in that batch (allocate first)")
        preference.batch_id = batch_id
    if status == "Not Possible" and not note:
        raise ValidationError("A reason is required", {"status_note": ["Tell the student why"]})
    _set(preference, status, note)
    delivery_notices.notify_student(enrolment.student_id, title=f"Your slot request is {status}",
                                    body=(note or "") + (" A waitlist place is not a seat." if status == "Waitlisted" else ""),
                                    event_key=f"slot-preference-{preference.preference_id}-{status}", link="/schedule",
                                    branch_id=enrolment.service_branch_id)
    return preference


def seat_taken(enrolment_id: int, batch_id: int) -> None:
    """An allocation to the batch the student asked for confirms their open request."""
    preference = db.session.execute(select(SlotPreference).where(
        SlotPreference.enrolment_id == enrolment_id, SlotPreference.batch_id == batch_id, SlotPreference.status.in_(OPEN))).scalar_one_or_none()
    if preference is not None:
        _set(preference, "Confirmed", "Seat allocated")


def _set(preference: SlotPreference, status: str, note: str | None) -> None:
    old = preference.status
    preference.status, preference.status_note = status, note
    preference.status_by, preference.status_at = actor_id(), datetime.now(timezone.utc)
    db.session.flush()
    audit.record("SLOT_PREFERENCE_STATUS", "slot_preference", preference.preference_id, old={"status": old}, new={"status": status},
                 reason=note)
