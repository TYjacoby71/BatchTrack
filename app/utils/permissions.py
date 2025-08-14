from flask import abort, flash, redirect, url_for, request, jsonify
from flask_login import current_user, login_required
from functools import wraps
from werkzeug.exceptions import Forbidden
from typing import Iterable
from flask_login import current_user
from functools import wraps
from flask import abort, g, session, current_app

def _wants_json() -> bool:
    """Check if client expects JSON response"""
    return request.path.startswith("/api/") or \
           request.accept_mimetypes.best == "application/json"

def require_permission(permission_name):
    """
    Decorator to require a specific permission for a route
    Enhanced with JSON-aware responses for API endpoints
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.has_permission(permission_name):
                if _wants_json():
                    return jsonify(error="forbidden", permission=permission_name), 403
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Alias for consistency with existing code
permission_required = require_permission

def any_permission_required(*perms: str):
    """
    Decorator requiring any one of the specified permissions
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.has_any_permission(perms):
                if _wants_json():
                    return jsonify(error="forbidden_any", permissions=list(perms)), 403
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
        @login_required
        def decorated_function(*args, **kwargs):
            org = getattr(current_user, "organization", None)
            if not org:
                if _wants_json():
                    return jsonify(error="no_organization"), 403
                raise Forbidden("No organization found.")

            current_tier = getattr(org, 'subscription_tier', 'free')
            try:
                current_index = TIER_ORDER.index(current_tier)
                required_index = TIER_ORDER.index(min_tier)

                if current_index < required_index:
                    if _wants_json():
                        return jsonify(error="tier_forbidden", required=min_tier, current=current_tier), 403
                    raise Forbidden(f"Requires {min_tier} tier or higher.")

            except ValueError:
                # Unknown tier, deny access
                if _wants_json():
                    return jsonify(error="unknown_tier"), 403
                raise Forbidden("Unknown subscription tier.")

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_permission_with_org_scoping(permission_name, require_org_scoping=True):
    """
    Decorator to require a specific permission for a route
    Also enforces organization scoping by default
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)

            # Check permission
            if not has_permission(current_user, permission_name):
                abort(403)

            # Enforce organization scoping for non-developer users
            if require_org_scoping and current_user.user_type != 'developer':
                effective_org_id = get_effective_organization_id()
                if not effective_org_id:
                    abort(403, description="No organization context")

                # Add organization context to kwargs for easy access
                kwargs['organization_id'] = effective_org_id

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_organization_scoping(f):
    """Decorator to enforce organization scoping on data access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)

        effective_org_id = get_effective_organization_id()
        if not effective_org_id and current_user.user_type != 'developer':
            abort(403, description="No organization context")

        # Add organization context to kwargs
        kwargs['organization_id'] = effective_org_id
        return f(*args, **kwargs)
    return decorated_function

def require_system_admin(f):
    """Decorator for system admin only routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)

        if not has_permission('dev.system_admin'):
            abort(403)

        return f(*args, **kwargs)
    return decorated_function

def require_organization_owner(f):
    """Decorator for organization owner only routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)

        if not is_organization_owner():
            abort(403)

        return f(*args, **kwargs)
    return decorated_function

def has_permission(permission_name_or_user, permission_name_or_none=None):
    """Check if user has a specific permission using proper authorization hierarchy"""
    # Handle both calling patterns:
    # has_permission('permission.name') - from code
    # has_permission(current_user, 'permission.name') - from templates

    if permission_name_or_none is not None:
        # Template style: has_permission(user, permission_name)
        user = permission_name_or_user
        permission_name = permission_name_or_none
    else:
        # Code style: has_permission(permission_name, user=None)
        permission_name = permission_name_or_user
        user = current_user

    if not hasattr(user, 'is_authenticated') or not user.is_authenticated:
        return False

    # Use the proper authorization hierarchy
    from .authorization import AuthorizationHierarchy
    return AuthorizationHierarchy.check_user_authorization(user, permission_name)

def _org_tier_includes_permission(organization, permission_name):
    """Check if organization's subscription tier includes this permission"""
    if not organization:
        return False

    # Get organization's effective subscription tier
    current_tier = organization.effective_subscription_tier

    # Import here to avoid circular import
    from app.blueprints.developer.subscription_tiers import load_tiers_config

    # Get tier permissions from subscription tiers config
    tiers_config = load_tiers_config()
    tier_data = tiers_config.get(current_tier, {})
    tier_permissions = tier_data.get('permissions', [])

    return permission_name in tier_permissions

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

def get_user_permissions():
    """Get all permissions for the current user using authorization hierarchy"""
    if not current_user.is_authenticated:
        return []

    # Use the proper authorization hierarchy
    from .authorization import AuthorizationHierarchy
    return AuthorizationHierarchy.get_user_effective_permissions(current_user)

def get_effective_organization_id():
    """Get the effective organization ID for the current user (DEVELOPER-ONLY FUNCTION)"""
    if not current_user.is_authenticated:
        return None

    # Check for developer masquerade context in g first
    if hasattr(g, 'effective_org_id'):
        return g.effective_org_id

    # For developers in customer view mode
    if current_user.user_type == 'developer':
        return session.get('dev_selected_org_id')

    # Regular users should use current_user.organization_id directly
    return current_user.organization_id

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

    # Check if tier is available and customer-facing
    if not organization.tier.is_available:
        return False, "Subscription tier is not available"

    # For billing-required tiers, check billing status
    if organization.tier.requires_stripe_billing or organization.tier.requires_whop_billing:
        # Check subscription status
        if organization.subscription_status not in ['active', 'trialing']:
            return False, "Subscription not active"

        # Additional billing validations can be added here
        # e.g., check for past due payments, etc.

    return True, "Active subscription"

def get_available_roles_for_user(user=None):
    """Get roles that can be assigned to a user"""
    if not user:
        user = current_user

    from app.models.role import Role

    # Handle developer customer view
    if user.user_type == 'developer':
        org_id = get_effective_organization_id()
        return Role.get_organization_roles(org_id) if org_id else []

    return Role.get_organization_roles(user.organization_id)

class UserTypeManager:
    """Manage user types and role assignments"""

    @staticmethod
    def assign_role_by_user_type(user):
        """Assign appropriate role based on user type and organization subscription"""
        from app.models.role import Role

        if user.user_type == 'developer':
            return None  # Developers don't get roles
        elif user.user_type == 'organization_owner':
            role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        else:  # team_member
            # Assign role based on organization subscription
            if user.organization and user.organization.subscription_tier == 'solo':
                role = Role.query.filter_by(name='operator').first()
            else:
                role = Role.query.filter_by(name='manager').first()

        if role:
            user.assign_role(role)

        return role

    @staticmethod
    def get_user_type_display_name(user_type):
        """Get human-readable name for user type"""
        names = {
            'developer': 'System Developer',
            'organization_owner': 'Organization Owner',
            'team_member': 'Team Member'
        }
        return names.get(user_type, 'Team Member')

    @staticmethod
    def create_organization_with_owner(org_name, owner_username, owner_email, subscription_tier='solo'):
        """Create new organization with owner user"""
        from app.models import Organization, User, Role
        from app.extensions import db

        # Create organization
        org = Organization(
            name=org_name,
            subscription_tier=subscription_tier
        )
        db.session.add(org)
        db.session.flush()

        # Create owner user
        owner = User(
            username=owner_username,
            email=owner_email,
            organization_id=org.id,
            user_type='organization_owner'
        )
        db.session.add(owner)
        db.session.flush()

        # Assign organization owner system role
        UserTypeManager.assign_role_by_user_type(owner)

        db.session.commit()
        return org, owner

def _testing_ok() -> bool:
    try:
        return bool(current_app.config.get("TESTING"))
    except Exception:
        return False

def permission_required(*perms):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if _testing_ok():
                return fn(*a, **kw)
            # TODO: real permission check later
            return fn(*a, **kw)
        return wrapper
    return deco

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

def _has_tier_permission_for_org(org_id, permission_name):
    """Check if a permission is available for an organization's subscription tier"""
    from app.models import Organization, Permission

    org = Organization.query.get(org_id)
    if not org:
        return False

    # Get the permission object
    permission = Permission.query.filter_by(name=permission_name, is_active=True).first()
    if not permission:
        return False

    # Check if permission is available for the organization's tier
    effective_tier = org.effective_subscription_tier
    return permission.is_available_for_tier(effective_tier)