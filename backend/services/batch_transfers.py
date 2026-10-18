"""Batch transfer requests (Module 15 §13). Moving an allocated student, or one combo track, to another batch is requested and
then approved by the Branch Manager of the student's service branch (or a Super Admin), never by the requester. A track can
be placed in another branch's batch when the destination first confirms it can deliver (the admission, its payments and the
other tracks stay where they are). A different curriculum version needs the receiving Branch Manager's academic mapping first
(the review fails until then). Moving the whole admission to another branch comes from the CRM (AdmissionUpdated)."""
from datetime import datetime, timezone

from sqlalchemy import or_, select

from config.database import db
from models import BatchTransferRequest
from repositories import batches as batches_repo
from repositories import enrolments as enrolments_repo
from repositories import students as students_repo
from repositories import users as users_repo
from repositories.common import paginate
from services import allocations, approvals, audit, delivery_access, delivery_notices, scope
from services.batch_allocations import _enforce, _notify_seat, review
from services.batches import sync_full
from services.context import actor_id, current_user
from services.errors import BusinessRule, Conflict, Forbidden, NotFound, ValidationError


def _now() -> datetime:
    return datetime.now(timezone.utc)


def request_transfer(enrolment_id: int, data: dict) -> BatchTransferRequest:
    """Ask to move a seat (the whole enrolment, or one track with enrolment_track_id) to another batch, after its review."""
    enrolment = enrolments_repo.get_enrolment_for_update(enrolment_id)
    if enrolment is None:
        raise NotFound("Enrolment not found")
    scope.assert_can_view_enrolment(enrolment)
    delivery_access.assert_can_manage_branch(enrolment.service_branch_id)
    track_id = data.get("enrolment_track_id")
    if track_id is not None and not any(t.enrolment_track_id == track_id for t in enrolment.tracks):
        raise ValidationError("Unknown track", {"enrolment_track_id": ["Not a track of this enrolment"]})
    to_batch = batches_repo.get_batch(data["to_batch_id"])
    if to_batch is None:
        raise NotFound("Batch not found")
    interbranch = to_batch.branch_id != enrolment.service_branch_id
    if interbranch and track_id is None:
        raise BusinessRule("Moving the whole enrolment to another branch is a service-branch transfer: the CRM sends it")
    current = allocations.current_seat(enrolment, track_id)
    if current is None and not interbranch:
        raise Conflict("Nothing to move: the seat is not allocated yet; allocate it instead")
    report = review(to_batch, enrolment, transfer=current is not None, enrolment_track_id=track_id, interbranch=interbranch)
    _enforce(report, data.get("acknowledge_warnings", False))
    if db.session.execute(select(BatchTransferRequest).where(
            BatchTransferRequest.enrolment_id == enrolment_id, BatchTransferRequest.status == "Pending",
            BatchTransferRequest.enrolment_track_id.is_(None) if track_id is None else BatchTransferRequest.enrolment_track_id == track_id)).first():
        raise Conflict("A transfer of this seat is already waiting for a decision")

    request = BatchTransferRequest(enrolment_id=enrolment_id, enrolment_track_id=track_id, from_batch_id=current.batch_id if current else None,
                                   to_batch_id=to_batch.batch_id, interbranch=interbranch, reason=data["reason"],
                                   acknowledged_warnings=report["warnings"], requested_by=actor_id())
    db.session.add(request)
    db.session.flush()
    audit.record("BATCH_TRANSFER_REQUESTED", "batch_transfer_request", request.request_id, branch_id=enrolment.service_branch_id,
                 reason=data["reason"], new={"enrolment_id": enrolment_id, "enrolment_track_id": track_id, "to_batch_id": to_batch.batch_id,
                                             "interbranch": interbranch})
    who = f"{enrolment.enrolment_code} → {to_batch.batch_code}"
    if interbranch:
        _notify_branch(to_batch.branch_id, ("BRANCH_MANAGER",), f"Confirm delivery for a placed track: {who}",
                       data["reason"], f"transfer-request-{request.request_id}-destination")
    else:
        _notify_branch(enrolment.service_branch_id, ("BRANCH_MANAGER",), f"Approve batch transfer: {who}", data["reason"],
                       f"transfer-request-{request.request_id}")
    return request


def _notify_branch(branch_id: int, roles: tuple[str, ...], title: str, body: str, key: str) -> None:
    holders = [u for role in roles for u in users_repo.user_ids_with_role(role, branch_id)]
    delivery_notices.notify_users(holders, title=title, body=body, event_key=key, link="/branch/batches", branch_id=branch_id,
                                  category="Batch", action_required=True)


def _load(request_id: int) -> tuple[BatchTransferRequest, object]:
    request = db.session.execute(select(BatchTransferRequest).where(BatchTransferRequest.request_id == request_id)
                                 .with_for_update(of=BatchTransferRequest)).scalar_one_or_none()
    if request is None:
        raise NotFound("Transfer request not found")
    enrolment = students_repo.get_enrolment(request.enrolment_id)
    branch_ids = scope.visible_branch_ids()
    if branch_ids is not None and not ({enrolment.service_branch_id, request.to_batch.branch_id} & branch_ids):
        raise NotFound("Transfer request not found")
    if request.status != "Pending":
        raise BusinessRule(f"The request is already {request.status}")
    return request, enrolment


def confirm_destination(request_id: int, decision: str, note: str | None) -> BatchTransferRequest:
    """The destination branch (its Branch Manager) confirms it can deliver a placed track."""
    request, enrolment = _load(request_id)
    if not request.interbranch:
        raise BusinessRule("Only a track placed at another branch needs the destination's confirmation")
    approvals.require_decider(request.to_batch.branch_id, request.requested_by, "Only the destination branch confirms delivery")
    approvals.require_independent(request.requested_by, message="The requester cannot confirm their own request")
    if decision == "Rejected":
        return _reject(request, enrolment, note)
    request.destination_confirmed_by, request.destination_confirmed_at = actor_id(), _now()
    db.session.flush()
    _notify_branch(enrolment.service_branch_id, ("BRANCH_MANAGER",),
                   f"Approve track placement: {enrolment.enrolment_code} → {request.to_batch.batch_code}",
                   f"{request.to_batch.branch.branch_name} confirmed it can deliver. {request.reason}", f"transfer-request-{request.request_id}")
    return request


def decide(request_id: int, decision: str, note: str | None) -> BatchTransferRequest:
    """The Branch Manager of the student's service branch decides alone. Approving re-runs the review and
    moves the seat; the earlier allocation stays as history."""
    request, enrolment = _load(request_id)
    approvals.require_decider(enrolment.service_branch_id, request.requested_by,
                              "Only the Branch Manager of the student's branch decides a transfer")
    if decision == "Rejected":
        return _reject(request, enrolment, note)
    if request.interbranch and request.destination_confirmed_at is None:
        raise BusinessRule("The destination branch has not confirmed it can deliver yet")

    enrolment = enrolments_repo.get_enrolment_for_update(enrolment.enrolment_id)
    to_batch = batches_repo.get_batch_for_update(request.to_batch_id)
    old = allocations.current_seat(enrolment, request.enrolment_track_id)
    if (old.batch_id if old else None) != request.from_batch_id:
        raise Conflict("The seat has moved since the request; ask again")
    report = review(to_batch, enrolment, transfer=old is not None, enrolment_track_id=request.enrolment_track_id,
                    interbranch=request.interbranch)
    _enforce(report, acknowledge_warnings=True)  # the requester acknowledged the warnings; new failures still block
    request.status, request.decided_by, request.decided_at, request.decision_note = "Approved", actor_id(), _now(), note
    db.session.flush()  # the database reads the approval when it checks an interbranch seat
    allocation = allocations.allocate(enrolment, to_batch, created_by=actor_id(), reason=request.reason,
                                      enrolment_track_id=request.enrolment_track_id, interbranch=request.interbranch)
    if old is not None:
        old.reason = f"Moved to {to_batch.batch_code}: {request.reason}"
    request.applied_allocation_id = allocation.allocation_id
    db.session.flush()
    for batch_id in {request.from_batch_id, request.to_batch_id} - {None}:
        sync_full(batches_repo.get_batch(batch_id))
    audit.record("BATCH_TRANSFERRED", "batch_allocation", allocation.allocation_id, branch_id=to_batch.branch_id, reason=request.reason,
                 old={"batch_id": request.from_batch_id}, new={"batch_id": to_batch.batch_id, "enrolment_id": enrolment.enrolment_id,
                                                              "request_id": request.request_id, "approved_by": actor_id()})
    _notify_seat(enrolment, to_batch, f"You have moved to batch {to_batch.batch_code}", f"{enrolment.course.title}. Reason: {request.reason}",
                 f"allocation-{allocation.allocation_id}")
    delivery_notices.notify_users([request.requested_by], title=f"Transfer approved: {enrolment.enrolment_code} → {to_batch.batch_code}",
                                  body=note or "", event_key=f"transfer-request-{request.request_id}-decision", link="/branch/batches",
                                  branch_id=enrolment.service_branch_id, category="Batch")
    return request


def _reject(request: BatchTransferRequest, enrolment, note: str | None) -> BatchTransferRequest:
    if not note:
        raise ValidationError("A reason is required", {"note": ["Say why the transfer is not approved"]})
    request.status, request.decided_by, request.decided_at, request.decision_note = "Rejected", actor_id(), _now(), note
    db.session.flush()
    audit.record("BATCH_TRANSFER_REJECTED", "batch_transfer_request", request.request_id, branch_id=enrolment.service_branch_id, reason=note)
    delivery_notices.notify_users([request.requested_by], title=f"Transfer not approved: {enrolment.enrolment_code}", body=note,
                                  event_key=f"transfer-request-{request.request_id}-decision", link="/branch/batches",
                                  branch_id=enrolment.service_branch_id, category="Batch")
    return request


def list_requests(filters: dict, page: int, per_page: int):
    """Requests touching the user's branches: the student's service branch or the destination batch's branch."""
    from models import Batch, Enrolment

    stmt = (select(BatchTransferRequest).join(Enrolment, Enrolment.enrolment_id == BatchTransferRequest.enrolment_id)
            .join(Batch, Batch.batch_id == BatchTransferRequest.to_batch_id)
            .order_by(BatchTransferRequest.requested_at.desc(), BatchTransferRequest.request_id.desc()))
    branch_ids = scope.visible_branch_ids()
    if branch_ids is not None:
        stmt = stmt.where(or_(Enrolment.service_branch_id.in_(branch_ids or {0}), Batch.branch_id.in_(branch_ids or {0})))
    if filters.get("status"):
        stmt = stmt.where(BatchTransferRequest.status == filters["status"])
    if filters.get("batch_id"):
        stmt = stmt.where(or_(BatchTransferRequest.from_batch_id == filters["batch_id"], BatchTransferRequest.to_batch_id == filters["batch_id"]))
    items, meta = paginate(stmt, page, per_page)
    enrolments = {e.enrolment_id: e for e in (students_repo.get_enrolment(r.enrolment_id) for r in items)}
    return [(r, enrolments[r.enrolment_id]) for r in items], meta
