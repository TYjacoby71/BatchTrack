from flask_login import current_user
from functools import wraps

def has_permission(user_or_permission_name, permission_name=None):
    """
    Check if user has a specific permission through their assigned roles
    Supports both has_permission(permission_name) and has_permission(user, permission_name)
    """
    # Handle both calling patterns
    if permission_name is None:
        user = current_user
        permission = user_or_permission_name
    else:
        user = user_or_permission_name
        permission = permission_name

    if not user.is_authenticated:
        return False

    # Developers check their developer roles/permissions (system-wide, no tier restrictions)
    if user.user_type == 'developer':
        return user.has_developer_permission(permission)

    # All other users check organization roles with tier restrictions
    if not user.organization:
        return False

    # Check if subscription tier allows this permission
    if not _has_tier_permission(user, permission):
        return False

    # Check if any of the user's roles grants this permission
    roles = user.get_active_roles()
    for role in roles:
        if role.has_permission(permission):
            return True

    return False

def _has_tier_permission(user, permission_name):
    """Check if user's subscription tier allows this permission"""
    if not user.organization:
        return False

    # Get organization's effective subscription tier (handles subscription model fallback)
    current_tier = user.organization.effective_subscription_tier

    # Import here to avoid circular import
    from app.blueprints.developer.subscription_tiers import load_tiers_config

    # Get tier permissions
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
    """Check if current user has organization owner role (for UI context only)"""
    if not current_user.is_authenticated:
        return False

    # Developers in customer support mode act as organization owners
    if current_user.user_type == 'developer':
        from flask import session
        return session.get('dev_selected_org_id') is not None

    # Check if user has the organization_owner role
    return has_role('organization_owner')

def is_developer():
    """Check if current user is developer"""
    return current_user.is_authenticated and current_user.user_type == 'developer'

def require_permission(permission):
    """Decorator for permission checking"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not has_permission(permission):
                from flask import abort
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator

def get_user_permissions():
    """Get all permissions for the current user"""
    if not current_user.is_authenticated:
        return []

    if current_user.user_type == 'developer':
        from app.models.permission import Permission
        return [perm.name for perm in Permission.query.filter_by(is_active=True).all()]

    # Get permissions from assigned roles (works for all user types)
    # All permissions in the Permission model are now organization permissions
    permissions = set()
    roles = current_user.get_active_roles()
    for role in roles:
        for perm in role.get_permissions():
            if perm.is_available_for_tier(current_user.organization.subscription_tier):
                permissions.add(perm.name)

    return list(permissions)

def get_available_roles_for_user(user=None):
    """Get roles that can be assigned to a user"""
    if not user:
        user = current_user

    from app.models.role import Role
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