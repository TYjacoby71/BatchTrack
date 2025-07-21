from flask_login import current_user

def has_permission(user_or_permission_name, permission_name=None):
    """
    Check if user has a specific permission
    Supports both has_permission(permission_name) and has_permission(user, permission_name)

    Args:
        user_or_permission_name: Either a User object or permission name string
        permission_name (str, optional): Permission name if first arg is User

    Returns:
        bool: True if user has permission, False otherwise
    """
    # Handle both calling patterns
    if permission_name is None:
        # Called as has_permission('permission_name')
        user = current_user
        permission = user_or_permission_name
    else:
        # Called as has_permission(user, 'permission_name')
        user = user_or_permission_name
        permission = permission_name

    if not user.is_authenticated:
        return False

    # Developers have all permissions
    if user.user_type == 'developer':
        return True

    # Organization owners have all permissions for their subscription tier
    if user.user_type == 'organization_owner':
        # Check if permission is available for their subscription tier
        from app.models.permission import Permission
        perm_obj = Permission.query.filter_by(name=permission).first()
        if perm_obj:
            # Get user's organization subscription tier
            if user.organization:
                tier_permissions = get_subscription_tier_permissions(user.organization.subscription_tier)
                return permission in tier_permissions
        return False

    # Team members: check through role assignments
    return user_has_permission_through_roles(user, permission)

def has_role(role_name):
    """Check if current user has specific role"""
    if not current_user.is_authenticated:
        return False

    roles = current_user.get_active_roles()
    return any(role.name == role_name for role in roles)

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

    # Developers in customer support mode act as organization owners
    if current_user.user_type == 'developer':
        from flask import session
        return session.get('dev_selected_org_id') is not None

    return current_user.user_type == 'organization_owner'

def is_developer():
    """Check if current user is developer"""
    if not current_user.is_authenticated:
        return False
    return current_user.user_type == 'developer'

def require_permission(permission):
    """Decorator for permission checking"""
    from functools import wraps
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
        # Developers get all permissions
        from app.models.permission import Permission
        return [perm.name for perm in Permission.query.filter_by(is_active=True).all()]

    if current_user.user_type == 'organization_owner':
        # Organization owners get all permissions available to their subscription tier
        from app.models.permission import Permission
        available_perms = Permission.get_permissions_for_tier(current_user.organization.subscription_tier)
        return [perm.name for perm in available_perms]

    # Team members get permissions from their assigned roles
    permissions = set()
    roles = current_user.get_active_roles()
    for role in roles:
        for perm in role.get_permissions():
            if perm.is_available_for_tier(current_user.organization.subscription_tier):
                permissions.add(perm.name)

    return list(permissions)

def get_subscription_tier_permissions(subscription_tier):
    """Get all permissions available for a subscription tier"""
    from app.models.permission import Permission
    return [perm.name for perm in Permission.get_permissions_for_tier(subscription_tier)]

def user_has_permission_through_roles(user, permission_name):
    """Check if user has permission through their assigned roles"""
    if not user.organization_id:
        return False
        
    roles = user.get_active_roles()
    for role in roles:
        if role.has_permission(permission_name):
            # Also check if the permission is available for the organization's tier
            from app.models.permission import Permission
            permission = Permission.query.filter_by(name=permission_name).first()
            if permission and permission.is_available_for_tier(user.organization.subscription_tier):
                return True
    return False

def get_available_roles_for_user(user=None):
    """Get roles that can be assigned to a user"""
    if not user:
        user = current_user

    from ..models.role import Role
    return Role.get_organization_roles(user.organization_id)