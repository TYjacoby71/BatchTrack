from flask_login import current_user


def user_has_permission(user, permission_name):
    """Check if a user has a specific permission"""
    if not user or not user.is_authenticated:
        return False

    # Developer users have all permissions
    if user.user_type == 'developer':
        return True

    return user.has_permission(permission_name)


def require_organization_context(f):
    """Decorator to ensure user has organization context"""
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return False
        if not current_user.organization_id and current_user.user_type != 'developer':
            return False
        return f(*args, **kwargs)
    return wrapper


def check_organization_access(model_class, item_id):
    """
    Check if current user has access to an item based on organization.

    Args:
        model_class: The model class to check
        item_id: ID of the item to check

    Returns:
        bool: True if user has access, False otherwise
    """
    if not current_user or not current_user.is_authenticated:
        return False

    # Developers have access to everything
    if current_user.user_type == 'developer':
        return True

    # Regular users must have organization context
    if not current_user.organization_id:
        return False

    # Get the item and check organization
    item = model_class.query.get(item_id)
    if not item:
        return False

    # Check if item belongs to user's organization
    if hasattr(item, 'organization_id'):
        return item.organization_id == current_user.organization_id

    # If no organization_id field, assume public access for now
    return True