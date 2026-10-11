"""The Super Admin's overview: Needs action and the Setup checklist, the merged Setup & health list, and the staff list for pickers."""
from controllers.common import ok
from repositories import admin_users as users_repo
from services import admin_home, setup_health


def needs_action():
    return ok(admin_home.needs_action())


def setup():
    return ok(setup_health.checklist())


def staff_options():
    """Every active staff member, for a "who" picker (owner of a setup item, assignee of an issue)."""
    return ok([{"user_id": u.user_id, "full_name": u.full_name, "email": u.email,
                "roles": sorted({s.role.role_name for s in u.scopes if s.revoked_at is None})} for u in users_repo.active_staff()])
