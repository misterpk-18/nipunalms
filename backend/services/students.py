"""Student detail: the student, their admissions and the enrolments the current user may see."""
from dataclasses import dataclass

from models import Admission, Enrolment, Student
from repositories import batches as batches_repo
from repositories import students as students_repo
from services import scope
from services.errors import NotFound


@dataclass
class StudentDetail:
    student: Student
    admissions: list[tuple[Admission, str | None]]  # admission, its LMS status
    enrolments: list[tuple[Enrolment, dict | None]]  # enrolment, summary of the batch it is allocated to


def get_student(student_id: int) -> StudentDetail:
    student = students_repo.get_student(student_id)
    if student is None:
        raise NotFound("Student not found")
    scope.assert_can_view_student(student)

    enrolments = []
    for enrolment in students_repo.enrolments_of_student(student_id):
        try:
            scope.assert_can_view_enrolment(enrolment)
        except NotFound:
            continue  # e.g. a Guntur coordinator does not see this student's Vijayawada-serviced course
        enrolments.append(enrolment)

    allocations = batches_repo.active_allocations([e.enrolment_id for e in enrolments])
    visible_admission_ids = {e.admission_id for e in enrolments}
    admissions = [(a, students_repo.lms_status_of(a.admission_id))
                  for a in students_repo.admissions_of_student(student_id) if a.admission_id in visible_admission_ids]
    return StudentDetail(
        student=student,
        admissions=admissions,
        enrolments=[(e, allocations[e.enrolment_id].batch.to_summary() if e.enrolment_id in allocations else None)
                    for e in enrolments],
    )
