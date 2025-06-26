from flask_login import current_user
import json
import os

def load_permissions():
    """Load permissions from permissions.json as fallback"""
    try:
        permissions_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'permissions.json')
        with open(permissions_path, 'r') as f:
            return json.load(f)
    except:
        return {}

PERMISSIONS = load_permissions()

def has_permission(permission):
    """Check if current user has a specific permission"""
    if not current_user.is_authenticated:
        return False

    # First try database role system
    if hasattr(current_user, 'user_role') and current_user.user_role:
        return current_user.user_role.has_permission(permission)

    # Fallback to legacy JSON-based system
    user_role = getattr(current_user, 'role', 'operator')
    if not user_role:
        return False

    role_permissions = PERMISSIONS.get(user_role, [])

    # Check for wildcard permissions
    if '*' in role_permissions:
        return True

    # Check exact permission match
    if permission in role_permissions:
        return True

    # Check wildcard patterns (e.g., "alerts.*")
    for perm in role_permissions:
        if perm.endswith('.*'):
            prefix = perm[:-2]
            if permission.startswith(prefix + '.'):
                return True

    return False

def has_role(role_name):
    """Check if current user has specific role"""
    if not current_user.is_authenticated:
        return False

    # Try database-driven role first
    if hasattr(current_user, 'user_role') and current_user.user_role:
        return current_user.user_role.name == role_name

    # Fallback to string-based role
    return getattr(current_user, 'role', 'operator') == role_name

def has_subscription_feature(feature):
    """Check if current user's organization has subscription feature"""
    if not current_user.is_authenticated:
        return False
    # Placeholder - always return True for now
    return True

def is_organization_owner():
    """Check if current user is organization owner"""
    if not current_user.is_authenticated:
        return False
    return has_role('organization_owner')

def is_developer():
    """Check if current user is developer"""
    if not current_user.is_authenticated:
        return False
    return has_role('developer')

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

def user_scoped_query(model_class):
    """Return scoped query for the given model"""
    if hasattr(model_class, 'scoped'):
        return model_class.scoped()
    return model_class.query

def get_user_permissions():
    """Get all permissions for the current user"""
    if not current_user.is_authenticated:
        return []

    # Try database-driven permissions first
    if hasattr(current_user, 'user_role') and current_user.user_role:
        return [perm.name for perm in current_user.user_role.permissions]

    # Fallback to JSON-based permissions
    user_role = getattr(current_user, 'role', 'operator')
    return PERMISSIONS.get(user_role, [])