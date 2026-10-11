"""Completion & certificates as one pipeline (UX phase U15): where each student stands between "the course is done" and "the
certificate is in their hands".

Stages, in order:
  ready      a completion review is open (or the evidence says one could be started): the Branch Manager decides
  completed  the course is complete; the certificate waits for the Branch Manager's approval
  fee        a certificate cannot go on because the fee is not cleared (or a financial release is not granted)
  issue      approved and fee cleared: ready to issue
  issued     issued (or revoked, flagged)

Evidence is shown against the course's own thresholds (the completion profile of the curriculum version) as ticks and crosses;
nothing is a single score. This module only reads: deciding, approving, issuing and the rare corrections stay in
services/completion.py, services/certificates.py and services/certificate_requests.py, which the screen calls.
"""
from datetime import datetime, timezone

from sqlalchemy import select

from config.database import db
from models import Certificate, CompletionReview, Enrolment, EnrolmentProgress, Student
from repositories import attendance as attendance_repo
from repositories import batches as batches_repo
from repositories import certificates as certificates_repo
from repositories import completion as completion_repo
from repositories import progress as progress_repo
from repositories import settings as settings_repo
from services import certificates, completion, progress, scope
from services.context import current_user
from services.errors import Forbidden, ValidationError

STAGES = ("ready", "completed", "fee", "issue", "issued")
LABELS = {"ready": "Ready to decide", "completed": "Completed", "fee": "Waiting for fee", "issue": "Ready to issue", "issued": "Issued"}
PRE_ISSUE = ("Eligibility Review", "Awaiting Approval", "Approved for Issue")


def _threshold(enrolment: Enrolment) -> int:
    profile = (enrolment.curriculum_version.completion_profile if enrolment.curriculum_version_id else None) or {}
    value = profile.get("attendance_minimum_pct")
    return int(value) if value not in (None, "") else settings_repo.get_int("attendance_alert_threshold", 75)


def evidence(enrolment: Enrolment, progress_row: EnrolmentProgress | None, review: CompletionReview | None, open_recoveries: int) -> dict:
    """The checks a completion decision rests on, each with its value, its threshold and a tick or cross."""
    measures = progress.measures_of(progress_row) if progress_row is not None else None
    attendance = measures["attendance"]["percent"] if measures else None
    required = measures["required_learning"]["percent"] if measures else None
    minimum = _threshold(enrolment)
    trainer_ok = review is not None and review.trainer_recommendation == "Complete" and completion._trainer_confirmed(review, enrolment)
    checks = [
        {"key": "attendance", "label": "Attendance", "value": attendance, "threshold": minimum, "unit": "%",
         "ok": attendance is not None and attendance >= minimum,
         "detail": "Some classes are not marked yet, so this figure is provisional" if measures and measures["attendance"]["provisional"] else None},
        {"key": "required_learning", "label": "Required topics covered", "value": required, "threshold": 100, "unit": "%",
         "ok": required is not None and required >= 100, "detail": None},
        {"key": "recoveries", "label": "Missed classes made up", "value": open_recoveries, "threshold": 0, "unit": "open",
         "ok": open_recoveries == 0, "detail": f"{open_recoveries} recovery still to finish" if open_recoveries else None},
        {"key": "trainer", "label": "Trainer recommends complete", "value": review.trainer_recommendation if review else None,
         "threshold": "Complete", "unit": "", "ok": trainer_ok,
         "detail": None if trainer_ok else ("Waiting for the batch trainer's recommendation" if review is None or review.trainer_recommendation is None
                                           else f"The trainer said: {review.trainer_recommendation}")},
    ]
    return {"checks": checks, "all_ok": all(c["ok"] for c in checks)}


def _stage_of_certificate(certificate: Certificate) -> tuple[str, dict]:
    clearance = certificates.fee_clearance(certificate)
    if certificate.status in ("Issued", "Revoked"):
        return "issued", clearance
    if not clearance["cleared"]:
        return "fee", clearance
    return ("issue" if certificate.status == "Approved for Issue" else "completed"), clearance


def _entries(branch_ids, filters: dict) -> list[dict]:
    """Every pipeline entry in scope with its stage (cheap facts only); details are added for the page being shown."""
    condition = progress.visible_enrolment_condition()
    q = (filters.get("q") or "").strip().lower()
    entries: list[dict] = []

    def wanted(student: Student, enrolment: Enrolment) -> bool:
        if filters.get("course_id") and enrolment.course_id != filters["course_id"]:
            return False
        if filters.get("branch_id") and enrolment.service_branch_id != filters["branch_id"]:
            return False
        return not q or q in student.full_name.lower() or q in student.student_code.lower()

    open_reviews = db.session.execute(select(CompletionReview).join(Enrolment, Enrolment.enrolment_id == CompletionReview.enrolment_id)
                                      .where(CompletionReview.status == "Open", condition)).scalars().unique().all()
    reviewed = {r.enrolment_id for r in open_reviews}
    for review in open_reviews:
        enrolment = review.enrolment
        student = db.session.get(Student, enrolment.student_id)
        if wanted(student, enrolment):
            entries.append({"stage": "ready", "enrolment": enrolment, "student": student, "review": review, "certificate": None,
                            "since": review.created_at})

    # Running enrolments whose evidence is already complete but nobody has opened a review for yet
    stmt = (select(Enrolment).join(EnrolmentProgress, EnrolmentProgress.enrolment_id == Enrolment.enrolment_id)
            .where(condition, Enrolment.status == "Active", EnrolmentProgress.required_pct >= 100))
    for enrolment in db.session.execute(stmt).scalars().unique():
        if enrolment.enrolment_id in reviewed:
            continue
        student = db.session.get(Student, enrolment.student_id)
        if not wanted(student, enrolment):
            continue
        row = progress_repo.get_progress(enrolment.enrolment_id)
        if evidence(enrolment, row, None, attendance_repo.open_recovery_count(enrolment.enrolment_id))["checks"][0]["ok"]:
            entries.append({"stage": "ready", "enrolment": enrolment, "student": student, "review": None, "certificate": None,
                            "since": row.last_activity_at or enrolment.updated_at})

    cert_stmt = (select(Certificate).join(Student, Student.student_id == Certificate.student_id)
                 .where(Certificate.status.in_(PRE_ISSUE + ("Issued", "Revoked")))
                 .order_by(Certificate.certificate_id))
    if branch_ids is not None:
        cert_stmt = cert_stmt.where(Certificate.branch_id.in_(branch_ids))
    for certificate in db.session.execute(cert_stmt).scalars().unique():
        if not wanted(certificate.student, certificate.enrolment):
            continue
        stage, clearance = _stage_of_certificate(certificate)
        entries.append({"stage": stage, "enrolment": certificate.enrolment, "student": certificate.student, "review": None,
                        "certificate": certificate, "fee": clearance, "since": certificate.updated_at})
    return entries


def _detail(entry: dict, progress_rows: dict, reviews: dict, allocations: dict) -> dict:
    enrolment, student, certificate = entry["enrolment"], entry["student"], entry["certificate"]
    review = entry["review"] or reviews.get(enrolment.enrolment_id)
    row = progress_rows.get(enrolment.enrolment_id)
    allocation = allocations.get(enrolment.enrolment_id)
    can_decide = completion._can_decide(enrolment)
    data = {
        "key": f"cert-{certificate.certificate_id}" if certificate else f"enrol-{enrolment.enrolment_id}",
        "stage": entry["stage"], "since": entry["since"],
        "student": student.to_summary(), "enrolment": enrolment.to_summary(), "branch_id": enrolment.service_branch_id,
        "batch": allocation.batch.to_summary() if allocation else None,
        "evidence": evidence(enrolment, row, review, attendance_repo.open_recovery_count(enrolment.enrolment_id))
        if entry["stage"] in ("ready", "completed") else None,
        "review": None, "certificate": None, "fee": entry.get("fee"), "actions": [],
    }
    if review is not None and entry["stage"] == "ready":
        data["review"] = {"review_id": review.review_id, "trainer_recommendation": review.trainer_recommendation, "trainer_comment": review.trainer_comment,
                          "recommended_by": review.recommender.full_name if review.recommender else None}
    if certificate is not None:
        actions = certificates.actions_for(certificate)
        data["certificate"] = {"certificate_id": certificate.certificate_id, "status": certificate.status, "number": certificate.certificate_number,
                               "version": certificate.version, "type": certificate.certificate_type, "issue_date": certificate.issue_date,
                               "pending_request": certificates_repo.pending_request(certificate.certificate_id) is not None}
        data["actions"] = actions
        data["can_request_fee_exception"] = (entry["stage"] == "fee" and current_user().has_role(*certificates.REVIEWERS, branch_id=certificate.branch_id))
    elif entry["stage"] == "ready":
        data["actions"] = ["decide"] if (review is not None and can_decide) else (["start_review"] if can_decide else [])
    return data


def pipeline(filters: dict, page: int, per_page: int) -> tuple[list[dict], dict]:
    """The pipeline for the user's branches: one stage's rows (oldest wait first) and the count of every stage."""
    if not current_user().has_role("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO"):
        raise Forbidden("You don't have access to completion")
    stage = filters.get("stage") or "ready"
    if stage not in STAGES:
        raise ValidationError("Invalid request data", {"stage": [f"Must be one of: {', '.join(STAGES)}"]})
    if filters.get("branch_id"):
        scope.require_branch(filters["branch_id"])
    branch_ids = scope.visible_branch_ids()
    entries = _entries(branch_ids, filters)
    counts = {s: sum(1 for e in entries if e["stage"] == s) for s in STAGES}
    mine = sorted((e for e in entries if e["stage"] == stage), key=lambda e: (e["since"] or datetime.now(timezone.utc)))
    if stage == "issued":
        mine.reverse()  # newest issue first
    total = len(mine)
    shown = mine[(page - 1) * per_page: page * per_page]
    ids = [e["enrolment"].enrolment_id for e in shown]
    rows = _rows(shown, ids)
    return rows, {"page": page, "per_page": per_page, "total": total, "pages": -(-total // per_page), "counts": counts, "labels": LABELS}


def _rows(shown: list[dict], ids: list[int]) -> list[dict]:
    progress_rows = progress_repo.progress_by_enrolment(ids)
    reviews = completion_repo.latest_reviews(ids)
    allocations = batches_repo.active_allocations(ids)
    return [_detail(e, progress_rows, reviews, allocations) for e in shown]


def counts(branch_ids) -> dict[str, int]:
    """Stage counts for the navigation badge and My work."""
    entries = _entries(branch_ids, {})
    return {s: sum(1 for e in entries if e["stage"] == s) for s in STAGES}
