from flask import Blueprint

from controllers import admin_users as users_controller
from routes.decorators import fresh_auth, login_required, require_roles

admin_users_bp = Blueprint("admin_users", __name__, url_prefix="/admin/users")


@admin_users_bp.get("")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def list_users():
    return users_controller.list_users()


@admin_users_bp.get("/<int:user_id>")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def get_user(user_id: int):
    return users_controller.get_user(user_id)


@admin_users_bp.post("")
@login_required
@require_roles("SUPER_ADMIN")
@fresh_auth
def create_user():
    return users_controller.create_user()


@admin_users_bp.patch("/<int:user_id>")
@login_required
@require_roles("SUPER_ADMIN")
@fresh_auth
def update_user(user_id: int):
    return users_controller.update_user(user_id)


@admin_users_bp.post("/<int:user_id>/scopes")
@login_required
@require_roles("SUPER_ADMIN")
@fresh_auth
def grant_scope(user_id: int):
    return users_controller.grant_scope(user_id)


@admin_users_bp.post("/<int:user_id>/scopes/<int:scope_id>/revoke")
@login_required
@require_roles("SUPER_ADMIN")
@fresh_auth
def revoke_scope(user_id: int, scope_id: int):
    return users_controller.revoke_scope(user_id, scope_id)


@admin_users_bp.post("/<int:user_id>/deactivate")
@login_required
@require_roles("SUPER_ADMIN")
@fresh_auth
def deactivate(user_id: int):
    return users_controller.deactivate(user_id)


@admin_users_bp.post("/<int:user_id>/reactivate")
@login_required
@require_roles("SUPER_ADMIN")
@fresh_auth
def reactivate(user_id: int):
    return users_controller.reactivate(user_id)


@admin_users_bp.post("/<int:user_id>/reset-password")
@login_required
@require_roles("SUPER_ADMIN")
@fresh_auth
def reset_password(user_id: int):
    return users_controller.reset_password(user_id)
