from flask_login import current_user
from functools import wraps
from flask import abort

def require_permission(permission_name, require_org_scoping=True):
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
    """Check if user has a specific permission"""
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

    # Developers in customer view mode work like organization owners
    if user.user_type == 'developer':
        from flask import session
        selected_org_id = session.get('dev_selected_org_id')
        if selected_org_id:
            # Developer in customer view has all organization owner permissions for that tier
            return _has_tier_permission_for_org(selected_org_id, permission_name)
        else:
            # Developer in developer mode - check developer permissions
            return current_user.has_developer_permission(permission_name)

    # All other users: check org tier allows permission AND user has role with permission
    if not user.organization:
        return False

    # 1. First check: Does the organization's subscription tier include this permission?
    if not _org_tier_includes_permission(user.organization, permission_name):
        return False

    # 2. Second check: Does any of the user's roles grant this permission?
    roles = user.get_active_roles()
    for role in roles:
        if role.has_permission(permission_name):
            return True

    return False

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
        from flask import session
        return session.get('dev_selected_org_id') is not None

    # Organization owners are customers with the organization_owner role
    if current_user.user_type == 'customer':
        return any(role.name == 'organization_owner' for role in current_user.get_active_roles())

    return False

def is_developer():
    """Check if current user is developer"""
    return current_user.is_authenticated and current_user.user_type == 'developer'

def get_user_permissions():
    """Get all permissions for the current user"""
    if not current_user.is_authenticated:
        return []

    if current_user.user_type == 'developer':
        from flask import session
        if session.get('dev_selected_org_id'):
            # Developer in customer view - return permissions available to selected org's tier
            from app.models import Organization
            from app.models.permission import Permission
            selected_org = Organization.query.get(session.get('dev_selected_org_id'))
            if selected_org:
                permissions = set()
                all_permissions = Permission.query.filter_by(is_active=True).all()
                for perm in all_permissions:
                    if perm.is_available_for_tier(selected_org.effective_subscription_tier):
                        permissions.add(perm.name)
                return list(permissions)
            return []
        else:
            # Developer not in customer view - return all permissions
            from app.models.permission import Permission
            return [perm.name for perm in Permission.query.filter_by(is_active=True).all()]

    # Get permissions from assigned roles (works for all user types)
    permissions = set()
    roles = current_user.get_active_roles()
    for role in roles:
        for perm in role.get_permissions():
            # Only add permissions that the organization's tier allows
            if _org_tier_includes_permission(current_user.organization, perm.name):
                permissions.add(perm.name)

    return list(permissions)

def get_effective_organization_id():
    """Get the effective organization ID for current user (handles developer customer view)"""
    if not current_user.is_authenticated:
        return None

    if current_user.user_type == 'developer':
        # Developers can view customer data by selecting an organization
        from flask import session
        return session.get('dev_selected_org_id')
    else:
        # Regular users use their organization
        return current_user.organization_id

def get_effective_organization():
    """Get the effective organization for the current user (handles developer customer view)"""
    from app.models import Organization

    if not current_user.is_authenticated:
        return None

    org_id = get_effective_organization_id()
    if org_id:
        return Organization.query.get(org_id)
    return None

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
```

```python
from flask_login import current_user
from functools import wraps
from flask import abort

def require_permission(permission_name, require_org_scoping=True):
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
    """Check if user has a specific permission"""
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

    # Developers in customer view mode work like organization owners
    if user.user_type == 'developer':
        from flask import session
        selected_org_id = session.get('dev_selected_org_id')
        if selected_org_id:
            # Developer in customer view has all organization owner permissions for that tier
            return _has_tier_permission_for_org(selected_org_id, permission_name)
        else:
            # Developer in developer mode - check developer permissions
            return current_user.has_developer_permission(permission_name)

    # All other users: check org tier allows permission AND user has role with permission
    if not user.organization:
        return False

    # 1. First check: Does the organization's subscription tier include this permission?
    if not _org_tier_includes_permission(user.organization, permission_name):
        return False

    # 2. Second check: Does any of the user's roles grant this permission?
    roles = user.get_active_roles()
    for role in roles:
        if role.has_permission(permission_name):
            return True

    return False

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
        from flask import session
        return session.get('dev_selected_org_id') is not None

    # Organization owners are customers with the organization_owner role
    if current_user.user_type == 'customer':
        return any(role.name == 'organization_owner' for role in current_user.get_active_roles())

    return False

def is_developer():
    """Check if current user is developer"""
    return current_user.is_authenticated and current_user.user_type == 'developer'

def get_user_permissions():
    """Get all permissions for the current user"""
    if not current_user.is_authenticated:
        return []

    if current_user.user_type == 'developer':
        from flask import session
        if session.get('dev_selected_org_id'):
            # Developer in customer view - return permissions available to selected org's tier
            from app.models import Organization
            from app.models.permission import Permission
            selected_org = Organization.query.get(session.get('dev_selected_org_id'))
            if selected_org:
                permissions = set()
                all_permissions = Permission.query.filter_by(is_active=True).all()
                for perm in all_permissions:
                    if perm.is_available_for_tier(selected_org.effective_subscription_tier):
                        permissions.add(perm.name)
                return list(permissions)
            return []
        else:
            # Developer not in customer view - return all permissions
            from app.models.permission import Permission
            return [perm.name for perm in Permission.query.filter_by(is_active=True).all()]

    # Get permissions from assigned roles (works for all user types)
    permissions = set()
    roles = current_user.get_active_roles()
    for role in roles:
        for perm in role.get_permissions():
            # Only add permissions that the organization's tier allows
            if _org_tier_includes_permission(current_user.organization, perm.name):
                permissions.add(perm.name)

    return list(permissions)

def get_effective_organization_id():
    """Get the effective organization ID for current user (handles developer customer view)"""
    if not current_user.is_authenticated:
        return None

    if current_user.user_type == 'developer':
        # Developers can view customer data by selecting an organization
        from flask import session
        return session.get('dev_selected_org_id')
    else:
        # Regular users use their organization
        return current_user.organization_id

def get_effective_organization():
    """Get the effective organization for the current user (handles developer customer view)"""
    from app.models import Organization

    if not current_user.is_authenticated:
        return None

    org_id = get_effective_organization_id()
    if org_id:
        return Organization.query.get(org_id)
    return None

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

def has_permission(user, permission_name):
    """Check if user has a specific permission - billing-agnostic"""
    # Developers always have access
    if user.user_type == 'developer':
        return True

    # Organization owners get all permissions available to their tier
    if user.user_type == 'organization_owner' and user.organization:
        from ..services.billing_access_control import BillingAccessControl
        return BillingAccessControl.validate_tier_permission(user.organization, permission_name)

    # Regular users: check their assigned permissions
    if user.permissions:
        return any(p.name == permission_name for p in user.permissions)

    return False