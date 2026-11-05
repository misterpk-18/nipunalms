"""What waits for the Founder / CEO: reads for `GET /founder/inbox` (services/founder_inbox.py)."""
from sqlalchemy import select

from config.database import db
from models import (
    AttendanceCorrection, BatchCapacityRequest, BatchSuccession, BatchTransferRequest, CertificateChangeRequest,
    CertificateFinancialException, MaterialChange, SessionChangeRequest,
)


def pending_certificate_requests() -> list[CertificateChangeRequest]:
    stmt = (select(CertificateChangeRequest).where(CertificateChangeRequest.status == "Pending")
            .order_by(CertificateChangeRequest.requested_at, CertificateChangeRequest.request_id))
    return list(db.session.execute(stmt).scalars().unique())


def pending_fee_exceptions() -> list[CertificateFinancialException]:
    stmt = (select(CertificateFinancialException).where(CertificateFinancialException.status == "Pending")
            .order_by(CertificateFinancialException.requested_at, CertificateFinancialException.exception_id))
    return list(db.session.execute(stmt).scalars().unique())


def reschedule_requests_by(user_ids: list[int]) -> list[SessionChangeRequest]:
    """Open reschedule requests raised by these people (Branch Managers who also teach)."""
    if not user_ids:
        return []
    stmt = (select(SessionChangeRequest).where(SessionChangeRequest.status == "Open", SessionChangeRequest.requested_by.in_(user_ids))
            .order_by(SessionChangeRequest.created_at, SessionChangeRequest.request_id))
    return list(db.session.execute(stmt).scalars().unique())


def corrections_by(user_ids: list[int]) -> list[AttendanceCorrection]:
    """Pending attendance corrections raised by these people."""
    if not user_ids:
        return []
    stmt = (select(AttendanceCorrection).where(AttendanceCorrection.status == "Pending", AttendanceCorrection.requested_by.in_(user_ids))
            .order_by(AttendanceCorrection.requested_at, AttendanceCorrection.correction_id))
    return list(db.session.execute(stmt).scalars().unique())


# A batch request waits in these states: Pending, or Pending Approval for a material change (its students are asked only after)
BATCH_REQUESTS = ((BatchCapacityRequest, "Pending"), (BatchTransferRequest, "Pending"), (MaterialChange, "Pending Approval"),
                  (BatchSuccession, "Pending"))


def batch_requests_by(user_ids: list[int]) -> list:
    """Open capacity, transfer, material-change and merge / split requests raised by these people, oldest first."""
    if not user_ids:
        return []
    rows = []
    for model, waiting in BATCH_REQUESTS:
        stmt = select(model).where(model.status == waiting, model.requested_by.in_(user_ids)).order_by(model.requested_at)
        rows += db.session.execute(stmt).scalars().unique()
    return sorted(rows, key=lambda r: r.requested_at)
