"""
DEPRECATED: This file has been consolidated into app/utils/permissions.py
All authorization logic is now in a single source of truth.
"""

# Import everything from permissions for backward compatibility
from .permissions import (
    require_permission,
    role_required,
    has_permission,
    AuthorizationHierarchy,
    FeatureGate,
    get_effective_organization,
    get_effective_organization_id
)

# Maintain backward compatibility
def require_permission_decorator(permission_name):
    """Backward compatibility wrapper"""
    return require_permission(permission_name)