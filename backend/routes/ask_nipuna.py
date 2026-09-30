from flask import Blueprint

from controllers import ask_nipuna as ask_controller
from routes.decorators import login_required

ask_nipuna_bp = Blueprint("ask_nipuna", __name__, url_prefix="/ask-nipuna")


@ask_nipuna_bp.get("/status")
@login_required
def status():
    return ask_controller.status()


@ask_nipuna_bp.post("/queries")
@login_required
def ask():
    return ask_controller.ask()


@ask_nipuna_bp.get("/queries")
@login_required
def list_queries():
    return ask_controller.list_queries()


@ask_nipuna_bp.post("/queries/<int:ai_query_id>/feedback")
@login_required
def give_feedback(ai_query_id: int):
    return ask_controller.give_feedback(ai_query_id)
