from controllers.common import created, ok
from services import activation as activation_service
from services import students as students_service


def get_student(student_id: int):
    detail = students_service.get_student(student_id)
    return ok({
        **detail.student.to_dict(),
        "admissions": [a.to_dict(lms_status=lms_status) for a, lms_status in detail.admissions],
        "enrolments": [e.to_dict(batch=batch) for e, batch in detail.enrolments],
    })


def issue_activation(student_id: int):
    issued = activation_service.issue_as_staff(student_id)
    student = issued.activation.student
    return created({
        "student_id": student.student_id,
        "student_code": student.student_code,
        "token": issued.token,  # shown once: only its hash is stored
        "activation_path": f"/activate?token={issued.token}",
        "expires_at": issued.activation.expires_at,
        "activation_status": student.activation_status,
    })
