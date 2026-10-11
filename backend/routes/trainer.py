"""Trainer workspace reads (UX plan U13): the to-grade inbox, students at risk, batches and the batch / student pages."""
from flask import Blueprint

from controllers import trainer as trainer_controller
from routes.decorators import login_required, require_roles

trainer_bp = Blueprint("trainer", __name__, url_prefix="/trainer")


@trainer_bp.get("/to-grade")
@login_required
@require_roles("TRAINER")
def to_grade():
    return trainer_controller.to_grade()


@trainer_bp.get("/at-risk")
@login_required
@require_roles("TRAINER")
def at_risk():
    return trainer_controller.at_risk()


@trainer_bp.get("/batches")
@login_required
@require_roles("TRAINER")
def batches():
    return trainer_controller.batches()


@trainer_bp.get("/batches/<int:batch_id>")
@login_required
@require_roles("TRAINER")
def batch_page(batch_id: int):
    return trainer_controller.batch_page(batch_id)


@trainer_bp.get("/students/<int:student_id>")
@login_required
@require_roles("TRAINER")
def student_page(student_id: int):
    return trainer_controller.student_page(student_id)
