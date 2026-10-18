"""Search for the Ctrl/Cmd+K palette (`GET /search?q=`): the records a person may open, by name or code.

Pages are not searched here: the client lists the pages of the one workspace the session holds. A student gets no records. Records
are limited the way every list is: a Branch Manager sees their branches, a trainer the batches they teach and the students in
them, a Super Admin / Founder everything. Nothing outside that scope is returned, and nothing is a 403: it is simply absent.
"""
from repositories import batches as batches_repo
from repositories import search as search_repo
from services import scope
from services.context import current_user

MIN_LENGTH = 2
PER_KIND = 5


def search(text: str) -> list[dict]:
    text = text.strip()
    user = current_user()
    if len(text) < MIN_LENGTH or user.role_code == "STUDENT":
        return []
    branch_ids = scope.visible_branch_ids(user)
    batch_ids = scope.trainer_batch_ids(user)
    enrolment_ids = batches_repo.enrolment_ids_in_batches(batch_ids)
    results = []
    for student in search_repo.students(text, branch_ids, enrolment_ids, PER_KIND):
        results.append({"kind": "student", "id": student.student_id, "title": student.full_name,
                        "subtitle": f"{student.student_code} · {student.service_branch.branch_name}"})
    for batch in search_repo.batches(text, branch_ids, batch_ids, PER_KIND):
        results.append({"kind": "batch", "id": batch.batch_id, "title": batch.display_name or batch.batch_code,
                        "subtitle": f"{batch.batch_code} · {batch.course.title} · {batch.branch.branch_name}"})
    for certificate in search_repo.certificates(text, branch_ids, PER_KIND):
        results.append({"kind": "certificate", "id": certificate.certificate_id, "title": certificate.holder_name,
                        "subtitle": f"{certificate.certificate_number or 'Not issued yet'} · {certificate.course.title}"})
    return results
