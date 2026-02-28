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

from app.extensions import db
from app.models import Permission
from app.models.subscription_tier import SubscriptionTier
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
    all_permissions = Permission.query.filter_by(is_active=True).all()

    # Get current tier
    current_tier = (
        current_user.organization.effective_subscription_tier
        if current_user.organization
        else "free"
    )

    # Build tier permissions from DB only
    try:
        tier_id = int(current_tier) if isinstance(current_tier, str) else current_tier
    except Exception:
        logger.warning("Suppressed exception fallback at app/blueprints/developer/debug_routes.py:45", exc_info=True)
        tier_id = None
    tier_obj = db.session.get(SubscriptionTier, tier_id) if tier_id else None
    tier_permissions = (
        [p.name for p in getattr(tier_obj, "permissions", [])] if tier_obj else []
    )

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
    tiers_config = {}
    tiers = SubscriptionTier.query.all()
    for t in tiers:
        tiers_config[str(t.id)] = {
            "name": t.name,
            "permissions": [p.name for p in getattr(t, "permissions", [])],
            "billing_provider": t.billing_provider,
            "is_billing_exempt": t.is_billing_exempt,
            "is_customer_facing": t.is_customer_facing,
        }
    return jsonify(tiers_config)
