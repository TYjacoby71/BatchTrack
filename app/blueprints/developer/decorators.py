"""Developer-route authorization decorators.

Synopsis:
Provide thin decorator helpers that enforce authentication, permission checks,
and developer-only access constraints for blueprint view functions.

Glossary:
- Permission decorator: Wrapper enforcing a named capability on the request.
- Developer guard: Check that current user belongs to developer user type.
- Wrapped view: Original Flask route function executed after authorization.
"""

from __future__ import annotations

from functools import wraps

from app.utils.permissions import permission_required as _permission_required


# --- Permission decorator re-export ---
# Purpose: Provide local alias for canonical permission decorator import path.
# Inputs: Permission name string.
# Outputs: Decorator enforcing the named permission.
def permission_required(permission_name: str):
    """Re-export canonical permission decorator for convenience."""
    return _permission_required(permission_name)


# --- Require developer permission ---
# Purpose: Enforce canonical permission checks for developer routes.
# Inputs: Required permission name and wrapped route function.
# Outputs: Decorated view that delegates access control to permission system.
def require_developer_permission(permission_name: str):
    """Ensure the caller holds the given developer permission."""

    def decorator(view_func):
        @_permission_required(permission_name)
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            return view_func(*args, **kwargs)

        return wrapper

    return decorator
