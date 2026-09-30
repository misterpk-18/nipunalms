"""What the signed-in student is entitled to: their usable enrolments, the batch each is allocated to, and access windows.

Shared by the content library and the recordings; every student-facing list and open goes through this context, so an
enrolment that is withdrawn (or whose benefit gate is not met) never grants anything.
"""
from dataclasses import dataclass
from datetime import date

from config.timezone import today_ist
from models import Enrolment
from repositories import access_extensions as extensions_repo
from repositories import batches as batches_repo
from repositories import students as students_repo
from services import access
from services.context import current_user
from services.errors import Forbidden

UNUSABLE_STATUSES = ("Withdrawn", "Provisioning Pending")


@dataclass
class StudentContext:
    student_id: int
    enrolments: list[Enrolment]
    batch_by_enrolment: dict[int, int | None]  # the batch of the enrolment's active allocation
    windows: dict[int, access.AccessWindow]
    today: date

    def enrolment(self, enrolment_id: int) -> Enrolment | None:
        return next((e for e in self.enrolments if e.enrolment_id == enrolment_id), None)


def student_context() -> StudentContext:
    user = current_user()
    if user is None or user.student_id is None:
        raise Forbidden("This is a student view")
    enrolments = [e for e in students_repo.enrolments_of_student(user.student_id) if e.status not in UNUSABLE_STATUSES]
    allocations = batches_repo.active_allocations([e.enrolment_id for e in enrolments])
    return StudentContext(
        student_id=user.student_id,
        enrolments=enrolments,
        batch_by_enrolment={e.enrolment_id: allocations[e.enrolment_id].batch_id if e.enrolment_id in allocations else None
                            for e in enrolments},
        windows=access.windows_for(enrolments),
        today=today_ist(),
    )


def access_overview() -> list[dict]:
    """Per enrolment: Joining Date, the standard expiry, the current recording / material expiry, and what can still be requested."""
    ctx = student_context()
    overview = []
    for enrolment in ctx.enrolments:
        window = ctx.windows[enrolment.enrolment_id]
        pending = extensions_repo.pending_for_enrolment(enrolment.enrolment_id)
        overview.append({
            "enrolment": enrolment.to_summary(),
            "joining_date": window.joining_date,
            "first_expiry": window.first_expiry,
            "second_expiry": window.second_expiry,
            "recording": window.describe("Recording", ctx.today),
            "material": window.describe("Material", ctx.today),
            # a routine extra year can be requested once per kind, and only after joining
            "can_request": {kind: window.joining_date is not None and not window.extended(kind)
                            and not any(r.scope in (kind, "Both") for r in pending) for kind in access.KINDS},
            "pending_requests": [r.to_dict() for r in pending],
        })
    return overview
