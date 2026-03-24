"""Debug Routes module utilities.

Synopsis:
Provide documented top-level behavior for `app/blueprints/developer/debug_routes.py` without altering runtime logic.

Glossary:
- Module path: Source file `app/blueprints/developer/debug_routes.py`.
- Unit heading block: Standardized comment metadata above each top-level function/class.
"""

import logging

from flask import Blueprint, jsonify
from flask_login import current_user

from app.services.developer.debug_permission_service import DebugPermissionService
from app.utils.permissions import _org_tier_includes_permission, has_permission

from .decorators import require_developer_permission

logger = logging.getLogger(__name__)


debug_bp = Blueprint("debug", __name__, url_prefix="/debug")


# --- Debug Permissions ---
# Purpose: Implement `debug_permissions` behavior for this module.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@debug_bp.route("/permissions")
@require_developer_permission("dev.debug_mode")
def debug_permissions():
    """Debug endpoint to show current user's permissions"""
    # Get all permissions
    all_permissions = DebugPermissionService.list_active_permissions()

    # Get current tier
    current_tier = (
        current_user.organization.effective_subscription_tier
        if current_user.organization
        else "free"
    )

    tier_permissions = DebugPermissionService.resolve_tier_permissions(current_tier)

    # Check each permission
    permission_status = {}
    for perm in all_permissions:
        permission_status[perm.name] = {
            "has_permission": has_permission(current_user, perm.name),
            "has_tier_permission": (
                _org_tier_includes_permission(current_user.organization, perm.name)
                if current_user.organization
                else False
            ),
            "in_tier_config": perm.name in tier_permissions,
            "description": perm.description,
        }

    return jsonify(
        {
            "user_type": current_user.user_type,
            "current_tier": current_tier,
            "tier_permissions": tier_permissions,
            "permission_status": permission_status,
        }
    )


# --- Debug Tiers ---
# Purpose: Implement `debug_tiers` behavior for this module.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@debug_bp.route("/tiers")
@require_developer_permission("dev.debug_mode")
def debug_tiers():
    """Debug endpoint to show tier configuration"""
    tiers_config = DebugPermissionService.list_tier_configs()
    return jsonify(tiers_config)
