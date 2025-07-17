
from flask_login import current_user

def has_permission(permission_name):
    """Check if current user has a specific permission"""
    if not current_user.is_authenticated:
        return False
    
    return current_user.has_permission(permission_name)

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
    return current_user.user_type == 'organization_owner'

def is_developer():
    """Check if current user is developer"""
    if not current_user.is_authenticated:
        return False
    return current_user.user_type == 'developer'

def require_permission(permission):
    """Decorator for permission checking"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            if not has_permission(permission):
                from flask import abort
                abort(403)
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

def get_user_permissions():
    """Get all permissions for the current user"""
    if not current_user.is_authenticated:
        return []
    
    if current_user.user_type == 'developer':
        # Developers get all permissions
        from ..models.permission import Permission
        return [perm.name for perm in Permission.query.filter_by(is_active=True).all()]
    
    if current_user.user_type == 'organization_owner':
        # Organization owners get all permissions available to their subscription tier
        from ..models.permission import Permission
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

def get_available_roles_for_user(user=None):
    """Get roles that can be assigned to a user"""
    if not user:
        user = current_user
    
    from ..models.role import Role
    return Role.get_organization_roles(user.organization_id)
