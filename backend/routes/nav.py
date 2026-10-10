"""The shell: navigation count badges, the Getting started card and the Ctrl/Cmd+K search."""
from flask import Blueprint

from controllers import nav as nav_controller
from routes.decorators import login_required

nav_bp = Blueprint("nav", __name__)


@nav_bp.get("/me/nav-counts")
@login_required
def nav_counts():
    return nav_controller.nav_counts()


@nav_bp.get("/me/getting-started")
@login_required
def getting_started():
    return nav_controller.getting_started()


@nav_bp.get("/search")
@login_required
def search():
    return nav_controller.search()
