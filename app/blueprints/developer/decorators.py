from __future__ import annotations

from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user, login_required

from app.utils.permissions import permission_required as _permission_required


def permission_required(permission_name: str):
    """Re-export canonical permission decorator for convenience."""
    return _permission_required(permission_name)


def require_developer_permission(permission_name: str):
    """Ensure the caller is a developer and holds the given permission."""

    def decorator(view_func):
        @_permission_required(permission_name)
        @login_required
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if getattr(current_user, "user_type", None) != "developer":
                flash("Developer privileges required.", "error")
                return redirect(url_for("app_routes.dashboard"))
            return view_func(*args, **kwargs)

        return wrapper

    return decorator
