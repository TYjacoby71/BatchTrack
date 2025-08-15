
from flask import abort, flash, redirect, url_for, request, jsonify, session, current_app
from flask_login import current_user, login_required
from functools import wraps
from werkzeug.exceptions import Forbidden
from typing import Iterable
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class AppPermission(Enum):
    """Enumeration of application permissions"""
    # Product permissions
    PRODUCT_VIEW = "product.view"
    PRODUCT_CREATE = "product.create"
    PRODUCT_EDIT = "product.edit"
    PRODUCT_DELETE = "product.delete"
    
    # Batch permissions
    BATCH_VIEW = "batch.view"
    BATCH_CREATE = "batch.create"
    BATCH_START = "batch.start"
    BATCH_FINISH = "batch.finish"
    BATCH_CANCEL = "batch.cancel"
    
    # Inventory permissions
    INVENTORY_VIEW = "inventory.view"
    INVENTORY_EDIT = "inventory.edit"
    INVENTORY_ADJUST = "inventory.adjust"
    INVENTORY_DELETE = "inventory.delete"
    
    # Admin permissions
    ADMIN = "admin"
    USER_MANAGEMENT = "user.management"
    ROLE_MANAGEMENT = "role.management"
    
    # Organization permissions
    ORGANIZATION_VIEW = "organization.view"
    ORGANIZATION_EDIT = "organization.edit"
    ORGANIZATION_BILLING = "organization.billing"

def wants_json() -> bool:
    """Check if the request wants JSON response"""
    from app.utils.http import wants_json as http_wants_json
    return http_wants_json()

def require_permission(permission_name: str):
    """
    Decorator to require specific permissions with proper error handling
    Single source of truth for permission checking
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Allow everything during tests
            if current_app.config.get('TESTING', False):
                return f(*args, **kwargs)
            
            # Basic auth check
            if not current_user.is_authenticated:
                if wants_json():
                    return jsonify({"error": "Authentication required"}), 401
                flash("Please log in to access this page.", "error")
                return redirect(url_for("auth.login"))
            
            # Developer users have access to developer permissions
            if current_user.user_type == 'developer':
                # For developer permissions, just check if they're a developer
                if permission_name.startswith('developer.'):
                    return f(*args, **kwargs)
            
            # Check if user has the permission using authorization hierarchy
            if has_permission(current_user, permission_name):
                return f(*args, **kwargs)
            
            # Permission denied - return appropriate response
            if wants_json():
                return jsonify({"error": f"Permission denied: {permission_name}"}), 403
            
            flash(f"You don't have permission to access this feature. Required permission: {permission_name}", "error")
            return redirect(url_for("app_routes.dashboard"))
        
        return decorated_function
    return decorator

# Alias for backward compatibility
permission_required = require_permission

def any_permission_required(*permission_names):
    """Decorator that requires any one of the specified permissions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user or not current_user.is_authenticated:
                if wants_json():
                    return jsonify({"error": "unauthorized"}), 401
                return current_app.login_manager.unauthorized()

            # Check if user has any of the required permissions
            if not any(has_permission(current_user, perm) for perm in permission_names):
                if wants_json():
                    return jsonify({
                        "error": "forbidden",
                        "permissions": list(permission_names),
                        "message": f"Requires one of: {', '.join(permission_names)}"
                    }), 403
                raise Forbidden("You do not have any of the required permissions.")

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def tier_required(min_tier: str):
    """
    Decorator requiring minimum subscription tier
    """
    TIER_ORDER = ["free", "starter", "pro", "business", "enterprise"]

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if this should return JSON (API endpoints)
            wants_json_response = wants_json()

            # Check authentication first, with JSON-aware response
            if not current_user.is_authenticated:
                if wants_json_response:
                    return jsonify(error="unauthorized"), 401
                # For web requests, let Flask-Login handle the redirect
                return current_app.login_manager.unauthorized()

            org = getattr(current_user, "organization", None)
            if not org:
                if wants_json_response:
                    return jsonify(error="no_organization"), 403
                raise Forbidden("No organization found.")

            current_tier = getattr(org, 'subscription_tier', 'free')
            try:
                current_index = TIER_ORDER.index(current_tier)
                required_index = TIER_ORDER.index(min_tier)

                if current_index < required_index:
                    if wants_json_response:
                        return jsonify(error="tier_forbidden", required=min_tier, current=current_tier), 403
                    raise Forbidden(f"Requires {min_tier} tier or higher.")

            except ValueError:
                # Unknown tier, deny access
                if wants_json_response:
                    return jsonify(error="unknown_tier"), 403
                raise Forbidden("Unknown subscription tier.")

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def role_required(*roles):
    """
    Decorator to require specific roles
    Allows everything during testing
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Allow everything during tests
            if current_app.config.get('TESTING', False):
                return f(*args, **kwargs)
            
            # Basic auth check for non-test environments
            if not current_user.is_authenticated:
                abort(401)
            
            # TODO: Implement proper role checking
            # For now, just check if user is authenticated
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def has_permission(user, permission_name: str) -> bool:
    """
    Check if user has the given permission using the authorization hierarchy
    Single source of truth for permission checking logic
    """
    if not user or not hasattr(user, 'is_authenticated') or not user.is_authenticated:
        return False

    # Use the authorization hierarchy for permission checking
    return AuthorizationHierarchy.check_user_authorization(user, permission_name)

def get_user_permissions(user=None):
    """Get all permissions for the current user using authorization hierarchy"""
    if not user:
        user = current_user
        
    if not user or not user.is_authenticated:
        return []

    # Use the authorization hierarchy
    return AuthorizationHierarchy.get_user_effective_permissions(user)

def get_effective_organization_id():
    """Get the effective organization ID for the current user context"""
    # For developers viewing an organization
    if current_user.user_type == 'developer':
        return session.get('dev_selected_org_id')

    # For regular users
    return current_user.organization_id if current_user.organization_id else None

def get_effective_organization():
    """Get the effective organization for the current user"""
    from app.models import Organization

    if not current_user.is_authenticated:
        return None

    # Simple organization lookup without complex effective logic
    if current_user.user_type == 'developer':
        org_id = session.get('dev_selected_org_id')
    else:
        org_id = current_user.organization_id

    if org_id:
        return Organization.query.get(org_id)
    return None

def is_organization_owner():
    """Check if current user is organization owner"""
    if not current_user.is_authenticated:
        return False

    # Developers in customer view mode act as organization owners
    if current_user.user_type == 'developer':
        return session.get('dev_selected_org_id') is not None

    # Organization owners are customers with the organization_owner role
    if current_user.user_type == 'customer':
        return any(role.name == 'organization_owner' for role in current_user.get_active_roles())

    return False

def is_developer():
    """Check if current user is developer"""
    return current_user.is_authenticated and current_user.user_type == 'developer'

def has_role(role_name):
    """Check if current user has specific role"""
    if not current_user.is_authenticated:
        return False

    try:
        if hasattr(current_user, 'get_active_roles'):
            roles = current_user.get_active_roles()
            return any(role.name == role_name for role in roles)
    except Exception as e:
        print(f"Error checking role {role_name}: {e}")

    return False

def has_subscription_feature(feature):
    """Check if current user's organization has subscription feature"""
    if not current_user.is_authenticated:
        return False

    # Developers can access everything
    if current_user.user_type == 'developer':
        return True

    org_features = current_user.organization.get_subscription_features()
    return feature in org_features or 'all_features' in org_features

def _org_tier_includes_permission(organization, permission_name):
    """
    Check if organization's tier includes the specified permission
    Legacy function name for backward compatibility during transition
    """
    if not organization or not organization.tier:
        return False
    
    # Use the authorization hierarchy
    tier_permissions = AuthorizationHierarchy.get_tier_allowed_permissions(organization)
    return permission_name in tier_permissions

class AuthorizationHierarchy:
    """Handles the authorization hierarchy for the application"""

    @staticmethod
    def check_subscription_standing(organization):
        """
        Step 1: Check if subscription is in good standing
        """
        if not organization:
            return False, "No organization"

        # Exempt organizations always have access
        if organization.effective_subscription_tier == 'exempt':
            return True, "Exempt status"

        # Check if organization has valid subscription tier
        if not organization.tier:
            return False, "No subscription tier assigned"

        # Check if tier is available
        if not organization.tier.is_available:
            return False, "Subscription tier unavailable"

        # For paid tiers, check billing status
        if organization.tier.requires_stripe_billing or organization.tier.requires_whop_billing:
            if organization.subscription_status not in ['active', 'trialing']:
                return False, f"Subscription status: {organization.subscription_status}"

        return True, "Subscription in good standing"

    @staticmethod
    def get_tier_allowed_permissions(organization):
        """
        Step 2: Get all permissions allowed by subscription tier
        """
        if not organization or not organization.tier:
            return []

        # Load tier configuration to get permissions
        from app.blueprints.developer.subscription_tiers import load_tiers_config
        tiers_config = load_tiers_config()

        tier_key = organization.effective_subscription_tier
        tier_data = tiers_config.get(tier_key, {})

        return tier_data.get('permissions', [])

    @staticmethod
    def check_user_authorization(user, permission_name):
        """
        Complete authorization check following the hierarchy:
        1. Check subscription standing
        2. Check if tier allows permission
        3. Check if user role grants permission
        """

        # Developers have full access - they are super admins
        if user.user_type == 'developer':
            # For developer permissions, check if they have the specific developer permission
            if permission_name.startswith('developer.'):
                return True  # All developers get all developer permissions
            
            # For organization permissions when in customer view mode
            selected_org_id = session.get('dev_selected_org_id')
            if not selected_org_id:
                return True  # Developer mode - full access to all organization permissions too
            # If viewing a specific organization, continue with organization checks

        # Get organization (handle developer customer view)
        organization = get_effective_organization()

        if not organization:
            return False

        # Step 1: Check subscription standing
        subscription_ok, reason = AuthorizationHierarchy.check_subscription_standing(organization)
        if not subscription_ok:
            logger.warning(f"Subscription check failed for org {organization.id}: {reason}")
            return False

        # Step 2: Check if subscription tier allows this permission
        tier_permissions = AuthorizationHierarchy.get_tier_allowed_permissions(organization)
        if permission_name not in tier_permissions:
            logger.debug(f"Permission {permission_name} not allowed by tier {organization.effective_subscription_tier}")
            return False

        # Step 3: Check user role permissions
        # Organization owners get all tier-allowed permissions
        if user.user_type == 'organization_owner' or user.user_type == 'developer':
            return True

        # Other users need role-based permissions
        user_roles = user.get_active_roles()
        for role in user_roles:
            if role.has_permission(permission_name):
                return True

        return False

    @staticmethod
    def get_user_effective_permissions(user):
        """
        Get all effective permissions for a user based on the authorization hierarchy
        """
        # Developers in non-customer mode have full access
        if user.user_type == 'developer':
            selected_org_id = session.get('dev_selected_org_id')
            if not selected_org_id:
                from app.models.permission import Permission
                return [p.name for p in Permission.query.filter_by(is_active=True).all()]

        # Get organization
        organization = get_effective_organization()

        if not organization:
            return []

        # Check subscription standing
        subscription_ok, _ = AuthorizationHierarchy.check_subscription_standing(organization)
        if not subscription_ok:
            return []

        # Get tier-allowed permissions
        tier_permissions = AuthorizationHierarchy.get_tier_allowed_permissions(organization)

        # Organization owners get all tier-allowed permissions
        if user.user_type == 'organization_owner':
            return tier_permissions

        # Other users get intersection of tier permissions and role permissions
        user_permissions = set()
        user_roles = user.get_active_roles()

        for role in user_roles:
            role_permissions = [p.name for p in role.get_permissions()]
            # Only add permissions that are both in role AND allowed by tier
            for perm in role_permissions:
                if perm in tier_permissions:
                    user_permissions.add(perm)

        return list(user_permissions)

    @staticmethod
    def check_organization_access(organization):
        """Check if organization has valid access based on subscription and billing status"""
        if not organization:
            return False, "No organization found"

        # Exempt organizations always have access
        if organization.effective_subscription_tier == 'exempt':
            return True, "Exempt organization"

        # Check subscription tier exists and is valid
        if not organization.tier:
            return False, "No valid subscription tier"

        # Check if tier has valid integration setup
        if not organization.tier.has_valid_integration:
            return False, "Subscription tier integration not configured"

        # For billing-required tiers, check billing status
        if organization.tier.requires_stripe_billing or organization.tier.requires_whop_billing:
            # Check subscription status
            if organization.subscription_status not in ['active', 'trialing']:
                return False, "Subscription not active"

            # Additional billing validations can be added here
            # e.g., check for past due payments, etc.

        return True, "Active subscription"

class FeatureGate:
    """Feature gating based on subscription tiers"""

    @staticmethod
    def is_feature_available(feature_name, organization=None):
        """Check if a feature is available to the organization's subscription tier"""
        if not organization:
            organization = get_effective_organization()

        if not organization:
            return False

        # Check subscription standing first
        subscription_ok, _ = AuthorizationHierarchy.check_subscription_standing(organization)
        if not subscription_ok:
            return False

        # Load tier configuration
        from app.blueprints.developer.subscription_tiers import load_tiers_config
        tiers_config = load_tiers_config()

        tier_key = organization.effective_subscription_tier
        tier_data = tiers_config.get(tier_key, {})

        available_features = tier_data.get('features', [])
        return feature_name in available_features

    @staticmethod
    def check_usage_limits(limit_name, current_usage, organization=None):
        """Check if current usage is within subscription tier limits"""
        if not organization:
            organization = get_effective_organization()

        if not organization or not organization.tier:
            return False, "No subscription tier"

        # Example limit checks
        if limit_name == 'users':
            max_users = organization.tier.user_limit
            if max_users == -1:  # Unlimited
                return True, "Unlimited"
            return current_usage <= max_users, f"Limit: {max_users}"

        # Add other limit checks as needed
        return True, "No limits defined"

# Legacy compatibility functions
def require_permission_with_org_scoping(permission_name, require_org_scoping=True):
    """Legacy compatibility - use require_permission instead"""
    return require_permission(permission_name)

def require_organization_scoping(f):
    """Legacy compatibility - organization scoping is handled automatically"""
    return f

def require_system_admin(f):
    """Legacy compatibility - use require_permission('dev.system_admin') instead"""
    return require_permission('dev.system_admin')(f)

def require_organization_owner(f):
    """Legacy compatibility - check in the function itself"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_organization_owner():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
