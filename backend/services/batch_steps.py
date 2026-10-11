"""Where a batch is on its way to teaching (UX phase U14): Created -> Trainer -> Ready -> Confirmed -> Students -> Classes.

The step bar on the batch page and the one main button come from here, so the screen never has to work out what is next. The
problems are the points of the readiness record that still block a confirmation (a missing trainer, dates, room, recording
statement); the warnings are the advisory ones the Branch Manager may accept with a reason. Nothing here changes a batch.
"""
from repositories import batches as batches_repo
from repositories import class_sessions as sessions_repo
from services import batches as batches_service
from services import delivery_access
from services.context import current_user
from services.errors import NotFound

STEPS = (("created", "Created"), ("trainer", "Trainer"), ("ready", "Ready"), ("confirmed", "Confirmed"), ("students", "Students"), ("classes", "Classes"))
# What fixes each point of the readiness record: the trainer assignment, or the batch's own details
FIX = {"people": "trainer", "course_version": "details", "timetable": "details", "resources": "details", "conflicts": "details", "recording": "details"}


def _confirmed(batch) -> bool:
    return batch.confirmed_at is not None or batch.state not in ("Forming", "Proposed")


def progress(batch_id: int) -> dict:
    batch, allocated = batches_service.get_batch(batch_id)
    if delivery_access.is_student_only():
        raise NotFound("Batch not found")
    checklist = batches_service.confirmation_checklist(batch)
    review = [c for c in checklist if c["key"] != "approval"]
    problems = [{"key": c["key"], "label": c["label"].split(". ", 1)[-1], "detail": c["detail"], "status": c["status"], "fix": FIX.get(c["key"], "details")}
                for c in review if c["status"] in ("fail", "pending")]
    warnings = [{"key": c["key"], "label": c["label"].split(". ", 1)[-1], "detail": c["detail"]} for c in review if c["status"] == "warn"]
    lead = batches_repo.lead_trainer(batch.batch_id)
    counts = sessions_repo.state_counts_by_batch([batch.batch_id]).get(batch.batch_id, {"delivered": 0, "upcoming": 0, "cancelled": 0})
    classes = counts["delivered"] + counts["upcoming"]
    confirmed = _confirmed(batch)
    done = {"created": True, "trainer": lead is not None, "ready": confirmed or not problems, "confirmed": confirmed, "students": allocated > 0, "classes": classes > 0}
    steps = [{"key": key, "label": label, "done": done[key]} for key, label in STEPS]

    closed = batch.state in batches_service.CLOSED_STATES
    can_manage = delivery_access.can_manage_branch(batch.branch_id)
    can_confirm = current_user().has_role(*batches_service.CONFIRM_ROLES, branch_id=batch.branch_id)
    current = next((s["key"] for s in steps if not s["done"]), None)
    note = None
    nxt = None
    if closed:
        note = f"This batch is {batch.state.lower()}."
    elif batch.state == "On Hold":
        note = "This batch is on hold. Resume it to carry on."
    elif current == "trainer":
        nxt = {"key": "assign_trainer", "label": "Assign a lead trainer"}
    elif current == "ready":
        nxt = {"key": "finish_setup", "label": "Finish the setup"}
    elif current == "confirmed":
        nxt = {"key": "confirm", "label": "Confirm batch"} if can_confirm else None
        if nxt is None:
            note = "The Branch Manager confirms this batch."
    elif current == "students":
        nxt = {"key": "add_students", "label": "Add students from the waiting list"}
    elif current == "classes":
        nxt = {"key": "create_classes", "label": "Create classes"}
    return {"batch_id": batch.batch_id, "state": batch.state, "steps": steps, "current": current, "next": nxt if can_manage else None, "note": note,
            "problems": problems if not confirmed else [], "warnings": warnings if not confirmed else [],
            "can_confirm": can_confirm and not closed and not confirmed,
            "counts": {"students": allocated, "capacity": batch.capacity, "classes": classes, "upcoming": counts["upcoming"]}}
