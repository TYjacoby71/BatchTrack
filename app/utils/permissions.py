from flask_login import current_user

def has_permission(permission_name):
    """Check if current user has a specific permission"""
    if not current_user.is_authenticated:
        return False

    # Use database-driven permissions only
    if not hasattr(current_user, 'user_role') or not current_user.user_role:
        return False

    # Check database permissions
    if current_user.user_role.has_permission(permission_name):
        return True

    # Check for wildcard permissions in database
    for perm in current_user.user_role.permissions:
        if perm.name.endswith('.*'):
            prefix = perm.name[:-2]  # Remove ".*"
            if permission_name.startswith(prefix + '.'):
                return True

    return False

def has_role(role_name):
    """Check if current user has specific role"""
    if not current_user.is_authenticated:
        return False

    if not hasattr(current_user, 'user_role') or not current_user.user_role:
        return False

    return current_user.user_role.name == role_name

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

    if not hasattr(current_user, 'user_role') or not current_user.user_role:
        return []

    return [perm.name for perm in current_user.user_role.permissions]