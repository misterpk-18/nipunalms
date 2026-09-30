"""Route decorators: @login_required, @require_roles(...), @fresh_auth, @service_key_required.

Order on a route:  @login_required  →  @require_roles(...)  →  @fresh_auth  →  view
"""
import secrets
from functools import wraps

from flask import current_app, request

from services import auth as auth_service
from services.context import current_user
from services.errors import Forbidden, FreshAuthRequired, PasswordChangeRequired, Unauthenticated

# Endpoints a user with a pending forced password change may still call
PASSWORD_CHANGE_ALLOWED = {"auth.me", "auth.logout", "auth.change_password"}


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise Unauthenticated("Login required")

        user = auth_service.authenticate(token.strip())
        if user.must_change_password and request.endpoint not in PASSWORD_CHANGE_ALLOWED:
            raise PasswordChangeRequired("Change your temporary password to continue")
        return view(*args, **kwargs)

    return wrapper


def require_roles(*role_codes: str):
    """Allow if the user holds any of these roles at any branch; branch-level checks happen in services."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None or not user.has_role(*role_codes):
                raise Forbidden("You don't have access to this action")
            return view(*args, **kwargs)

        return wrapper

    return decorator


def fresh_auth(view):
    """Sensitive actions: the user must have entered their password recently (login or /auth/reauthenticate)."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None or not user.has_fresh_auth:
            raise FreshAuthRequired("Confirm your password to continue")
        return view(*args, **kwargs)

    return wrapper


def service_key_required(view):
    """Machine callers (the CRM): the X-Service-Key header must match CRM_SERVICE_KEY."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        expected = current_app.config.get("CRM_SERVICE_KEY")
        supplied = request.headers.get("X-Service-Key", "")
        if not expected or not secrets.compare_digest(supplied.encode(), expected.encode()):
            raise Unauthenticated("Invalid service key")
        return view(*args, **kwargs)

    return wrapper
