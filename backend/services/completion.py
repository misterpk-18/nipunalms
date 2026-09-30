"""Completion review: evidence-based decision that an enrolment is complete (never a single percentage).

The evidence shown is the four separate measures, the open recoveries and the trainer's recommendation. The
Academic Coordinator decides Complete / Not Yet / Needs Recovery; Complete moves the enrolment to Completed and
opens certificate eligibility in the Certificate Register. Decisions are audited; a decided review is final.
"""
import json
from datetime import datetime, timezone

from config.database import db
from models import CompletionReview, Enrolment
from repositories import attendance as attendance_repo
from repositories import batches as batches_repo
from repositories import completion as completion_repo
from repositories import progress as progress_repo
from repositories import students as students_repo
from repositories import users as users_repo
from repositories.common import paginate
from services import audit, certificates, progress, scope
from services.context import current_user
from services.errors import BusinessRule, Conflict, Forbidden, NotFound, ValidationError
from services.notifications import notify

DECIDERS = ("ACADEMIC_COORDINATOR", "SUPER_ADMIN")


def evidence_of(enrolment: Enrolment) -> dict:
    """The four measures plus what still blocks completion (open recoveries)."""
    measures = progress.measures_of(progress_repo.get_progress(enrolment.enrolment_id))
    return {**measures, "open_recoveries": attendance_repo.open_recovery_count(enrolment.enrolment_id)}


def _get_review(review_id: int) -> CompletionReview:
    review = completion_repo.get_review(review_id)
    if review is None:
        raise NotFound("Completion review not found")
    scope.assert_can_view_enrolment(review.enrolment)
    return review


def _is_batch_trainer(enrolment: Enrolment) -> bool:
    allocation = batches_repo.active_allocation(enrolment.enrolment_id)
    return allocation is not None and current_user().has_role("TRAINER") and allocation.batch_id in scope.trainer_batch_ids()


def _can_decide(enrolment: Enrolment) -> bool:
    return current_user().has_role(*DECIDERS, branch_id=enrolment.service_branch_id)


def _row(enrolment: Enrolment, review: CompletionReview | None, progress_row, batch: dict | None) -> dict:
    student = students_repo.get_student(enrolment.student_id)
    return {
        "student": student.to_summary(),
        "enrolment": enrolment.to_summary(),
        "batch": batch,
        "joining_date": enrolment.joining_date,
        "certificate_status": enrolment.certificate_status,
        "evidence": {**progress.measures_of(progress_row)} if progress_row else None,
        "review": review.to_dict() if review else None,
        "can_open": review is None or review.status == "Decided",
        "can_decide": _can_decide(enrolment) and review is not None and review.status == "Open",
    }


def list_candidates(filters: dict, page: int, per_page: int) -> tuple[list[dict], dict]:
    """Enrolments in scope that are running or completed, each with its evidence, latest review and certificate status."""
    condition = progress.visible_enrolment_condition()
    enrolments, meta = paginate(completion_repo.candidates_stmt(filters, condition), page, per_page)
    ids = [e.enrolment_id for e in enrolments]
    reviews = completion_repo.latest_reviews(ids)
    measures = progress_repo.progress_by_enrolment(ids)
    allocations = batches_repo.active_allocations(ids)
    rows = [_row(e, reviews.get(e.enrolment_id), measures.get(e.enrolment_id),
                 allocations[e.enrolment_id].batch.to_summary() if e.enrolment_id in allocations else None) for e in enrolments]
    return rows, meta


def get_review(review_id: int) -> dict:
    review = _get_review(review_id)
    return {**review.to_dict(), "live_evidence": evidence_of(review.enrolment) if review.status == "Open" else None,
            "can_decide": _can_decide(review.enrolment) and review.status == "Open"}


def open_review(enrolment_id: int) -> tuple[CompletionReview, bool]:
    """Open a review for a running enrolment (trainer of the batch or Academic Coordinator). Returns (review, created)."""
    enrolment = progress.get_visible_enrolment(enrolment_id)
    if not (_is_batch_trainer(enrolment) or _can_decide(enrolment)):
        raise Forbidden("Only the batch's trainer or the Academic Coordinator can open a completion review")
    existing = completion_repo.open_review(enrolment_id)
    if existing is not None:
        return existing, False
    if enrolment.status != "Active":
        raise BusinessRule(f"Enrolment {enrolment.enrolment_code} is '{enrolment.status}'; only an Active enrolment can be reviewed for completion")
    if not certificates.has_completion_rule(enrolment):
        raise BusinessRule(certificates.COMPLIMENTARY_PENDING)
    review = CompletionReview(enrolment_id=enrolment_id, opened_by=current_user().user_id)
    db.session.add(review)
    db.session.flush()
    audit.record("COMPLETION_REVIEW_OPENED", "completion_review", review.review_id, new={"enrolment": enrolment.enrolment_code},
                 branch_id=enrolment.service_branch_id)
    return review, True


def recommend(review_id: int, recommendation: str, comment: str | None) -> CompletionReview:
    """The trainer's recommendation (the coordinator may record one too); it informs the decision, it never makes it."""
    review = _get_review(review_id)
    enrolment = review.enrolment
    if not (_is_batch_trainer(enrolment) or _can_decide(enrolment)):
        raise Forbidden("Only the batch's trainer or the Academic Coordinator can recommend")
    if review.status != "Open":
        raise BusinessRule("This review is already decided")
    if recommendation != "Complete" and not comment:
        raise ValidationError("Invalid request data", {"comment": ["Say what is still missing"]})
    user = current_user()
    old = {"recommendation": review.trainer_recommendation}
    review.trainer_recommendation, review.trainer_comment = recommendation, comment
    review.recommended_by, review.recommended_at = user.user_id, datetime.now(timezone.utc)
    db.session.flush()
    audit.record("COMPLETION_RECOMMENDED", "completion_review", review.review_id, old=old, new={"recommendation": recommendation},
                 reason=comment, branch_id=enrolment.service_branch_id)
    notify(category="Completion", title=f"Completion recommendation: {students_repo.get_student(enrolment.student_id).full_name}",
           body=f"{recommendation}. {comment or ''}".strip(), link="/academic/completion", role_code="ACADEMIC_COORDINATOR",
           branch_id=enrolment.service_branch_id, event_key=f"completion-recommended:{review.review_id}:{review.recommended_at.isoformat()}",
           action_required=True)
    return review


def decide(review_id: int, decision: str, reason: str | None) -> CompletionReview:
    """Academic Coordinator's decision. Complete: the enrolment becomes Completed and certificate eligibility opens."""
    review = _get_review(review_id)
    enrolment = review.enrolment
    if not _can_decide(enrolment):
        raise Forbidden("Only the Academic Coordinator can decide a completion review")
    if review.status != "Open":
        raise Conflict("This review is already decided")
    if decision != "Complete" and not reason:
        raise ValidationError("Invalid request data", {"reason": ["Give the reason"]})
    if decision == "Complete":
        if enrolment.status != "Active":
            raise BusinessRule(f"Enrolment {enrolment.enrolment_code} is '{enrolment.status}' and cannot be completed")
        if not certificates.has_completion_rule(enrolment):
            raise BusinessRule(certificates.COMPLIMENTARY_PENDING)
        open_recoveries = attendance_repo.open_recovery_count(enrolment.enrolment_id)
        if open_recoveries:
            raise BusinessRule(f"Cannot complete: {open_recoveries} recovery(ies) still open for this enrolment")

    evidence = json.loads(json.dumps({**evidence_of(enrolment), "trainer_recommendation": review.trainer_recommendation,
                                      "as_of": datetime.now(timezone.utc)}, default=str))  # timestamps become text for JSONB
    review.status, review.decision, review.decision_reason = "Decided", decision, reason
    review.decided_by, review.decided_at, review.evidence = current_user().user_id, datetime.now(timezone.utc), evidence
    db.session.flush()

    old_status = enrolment.status
    if decision == "Complete":
        enrolment.status = "Completed"
        db.session.flush()
        certificates.open_eligibility(enrolment, review)
    audit.record("COMPLETION_DECIDED", "completion_review", review.review_id, old={"enrolment_status": old_status},
                 new={"decision": decision, "enrolment_status": enrolment.status, "evidence": evidence}, reason=reason,
                 branch_id=enrolment.service_branch_id)
    _notify_decision(review, enrolment)
    return review


def _notify_decision(review: CompletionReview, enrolment: Enrolment) -> None:
    if review.decision == "Complete":
        user = users_repo.get_by_student_id(enrolment.student_id)
        if user is not None:
            notify(category="Completion", title=f"Course completion confirmed: {enrolment.course.title}",
                   body="Your certificate eligibility is now being reviewed.", link="/certificates", branch_id=enrolment.service_branch_id,
                   recipient_user_ids=[user.user_id], event_key=f"completion-complete:{review.review_id}")
    elif review.recommended_by is not None and review.recommended_by != review.decided_by:
        notify(category="Completion", title=f"Completion review: {review.decision}",
               body=review.decision_reason, link="/trainer/students", branch_id=enrolment.service_branch_id,
               recipient_user_ids=[review.recommended_by], event_key=f"completion-decided:{review.review_id}")
