"""Mock interviews (Module 20 §8): the trainer offers slots, the student books one, the trainer confirms, holds it and records feedback.

Slot states: Open -> Slot Confirmation Pending (booked) -> Confirmed -> Completed. A mock interview is practice: feedback carries
no marks and does not make a result, and it says nothing about placement.
"""
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from config.database import db
from config.timezone import IST
from models import InterviewSlot
from repositories import tests as tests_repo
from repositories import users as users_repo
from services import assessment_scope as access
from services import notifications, scope, tests as tests_service
from services.context import current_user
from services.errors import BusinessRule, Conflict, Forbidden, NotFound, ValidationError


def _interview_test(test_id: int):
    test = tests_service.load_test(test_id)
    if test.kind != "Mock interview":
        raise BusinessRule("Slots belong to a mock interview")
    return test


def list_slots(test_id: int) -> list[dict]:
    """Staff: every slot with who booked it. Students: the slots still open, plus their own booking."""
    test = _interview_test(test_id)
    slots = tests_repo.slots_of(test_id)
    if access.is_student():
        seat = access.student_seat(test.batch_id)
        return [s.to_dict(viewer_is_student=True) for s in slots if s.status == "Open" or s.enrolment_id == seat.enrolment_id]
    return [s.to_dict() for s in slots]


def offer_slots(test_id: int, slots: list[dict], trainer_user_id: int | None) -> list[InterviewSlot]:
    """Offer interview times. The interviewer defaults to the caller and must be a trainer of the batch."""
    test = _interview_test(test_id)
    access.assert_can_manage(test.batch)
    if test.release_status == "Closed":
        raise BusinessRule("This mock interview is closed")
    interviewer = trainer_user_id or current_user().user_id
    if interviewer not in access.batch_trainer_ids(test.batch):
        raise ValidationError("Invalid request data", {"trainer_user_id": ["The interviewer must be a trainer of this batch"]})
    now = datetime.now(timezone.utc)
    created = []
    for item in slots:
        if item["ends_at"] <= item["starts_at"]:
            raise ValidationError("Invalid request data", {"slots": ["A slot must end after it starts"]})
        if item["starts_at"] <= now:
            raise ValidationError("Invalid request data", {"slots": ["A slot must start in the future"]})
        slot = InterviewSlot(test_id=test_id, trainer_user_id=interviewer, starts_at=item["starts_at"], ends_at=item["ends_at"])
        db.session.add(slot)
        created.append(slot)
    try:
        db.session.flush()
    except IntegrityError:
        raise Conflict("You already offer a slot at one of these times") from None
    tests_service.refresh_release_status(test)
    return created


def _slot(slot_id: int) -> InterviewSlot:
    slot = tests_repo.get_slot(slot_id)
    if slot is None:
        raise NotFound("Slot not found")
    if access.is_student():
        if slot.enrolment_id is None:
            access.student_seat(slot.test.batch_id)  # an open slot is visible to students of the batch
        elif slot.student_id != current_user().student_id:
            raise NotFound("Slot not found")
    else:
        scope.assert_can_view_batch(slot.test.batch)
    return slot


def _when(slot: InterviewSlot) -> str:
    return slot.starts_at.astimezone(IST).strftime("%d %b %Y %H:%M") + " IST"


def _notify_student(slot: InterviewSlot, title: str, body: str, key: str) -> None:
    user = users_repo.get_by_student_id(slot.student_id)
    if user:
        notifications.notify(category="Assessments", title=title, body=body, link=f"/tests/{slot.test_id}",
                             event_key=key, recipient_user_ids=[user.user_id], branch_id=slot.test.batch.branch_id)


def book_slot(slot_id: int) -> InterviewSlot:
    """A student takes an open slot; it waits for the trainer to confirm."""
    if not access.is_student():
        raise Forbidden("Only students book interview slots")
    slot = _slot(slot_id)
    test = slot.test
    if test.release_status != "Released":
        raise BusinessRule(f"This mock interview is {test.release_status}")
    if slot.status != "Open":
        raise BusinessRule("This slot is no longer open")
    if slot.starts_at <= datetime.now(timezone.utc):
        raise BusinessRule("This slot has already started")
    seat = access.student_seat(test.batch_id)
    slot.status, slot.enrolment_id, slot.student_id = "Slot Confirmation Pending", seat.enrolment_id, seat.student_id
    slot.booked_at = datetime.now(timezone.utc)
    try:
        db.session.flush()
    except IntegrityError:
        raise Conflict("You already have a booking for this mock interview") from None
    notifications.notify(category="Assessments", title="Interview slot to confirm",
                         body=f"{slot_student_name(slot)} booked {test.title} on {_when(slot)}.", link="/trainer/assessments",
                         event_key=f"slot-booked:{slot_id}:{seat.enrolment_id}", recipient_user_ids=[slot.trainer_user_id],
                         branch_id=test.batch.branch_id, action_required=True)
    return slot


def slot_student_name(slot: InterviewSlot) -> str:
    return slot.student.full_name if slot.student else "A student"


def _manageable_slot(slot_id: int) -> InterviewSlot:
    if access.is_student():
        raise Forbidden("Only staff can do this")
    slot = _slot(slot_id)
    access.assert_can_manage(slot.test.batch)
    return slot


def confirm_slot(slot_id: int) -> InterviewSlot:
    slot = _manageable_slot(slot_id)
    if slot.status != "Slot Confirmation Pending":
        raise BusinessRule(f"Only a booked slot can be confirmed (this one is {slot.status})")
    slot.status, slot.confirmed_at = "Confirmed", datetime.now(timezone.utc)
    db.session.flush()
    _notify_student(slot, "Interview slot confirmed", f"Your mock interview is confirmed for {_when(slot)}.", f"slot-confirmed:{slot_id}")
    return slot


def cancel_slot(slot_id: int, reason: str | None) -> InterviewSlot:
    """Staff withdraw a slot (the student is told). A student cancelling their own booking frees the slot for others."""
    if access.is_student():
        slot = _slot(slot_id)
        if slot.status not in ("Slot Confirmation Pending", "Confirmed"):
            raise BusinessRule("Only a booked slot can be cancelled")
        slot.status, slot.enrolment_id, slot.student_id = "Open", None, None
        slot.booked_at = slot.confirmed_at = None
        db.session.flush()
        return slot
    slot = _manageable_slot(slot_id)
    if slot.status in ("Completed", "Cancelled"):
        raise BusinessRule(f"A {slot.status.lower()} slot can't be cancelled")
    booked = slot.student_id is not None
    slot.status = "Cancelled"
    db.session.flush()
    if booked:
        _notify_student(slot, "Interview slot cancelled", f"Your mock interview on {_when(slot)} was cancelled{': ' + reason if reason else ''}. Please book another slot.",
                        f"slot-cancelled:{slot_id}")
    tests_service.refresh_release_status(slot.test)
    return slot


def complete_slot(slot_id: int, feedback: dict) -> InterviewSlot:
    """Record the interview: rating 1-5, strengths, improvement areas and the agreed next practice action."""
    slot = _manageable_slot(slot_id)
    if slot.status != "Confirmed":
        raise BusinessRule(f"Only a confirmed interview can be completed (this one is {slot.status})")
    slot.rating, slot.strengths = feedback["rating"], feedback["strengths"]
    slot.improvements, slot.next_action = feedback["improvements"], feedback["next_action"]
    slot.status, slot.completed_at = "Completed", datetime.now(timezone.utc)
    db.session.flush()
    _notify_student(slot, "Mock interview feedback", f"Your trainer recorded feedback for {slot.test.title}.", f"slot-feedback:{slot_id}")
    return slot
