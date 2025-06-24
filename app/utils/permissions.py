from functools import wraps
from flask import abort, request, jsonify, current_app
from flask_login import current_user
import json
import os

class PermissionManager:
    """Centralized permission management system"""

    def __init__(self):
        self.permissions_file = 'permissions.json'
        self._load_permissions()

    def _load_permissions(self):
        """Load permissions from file or create defaults"""
        try:
            with open(self.permissions_file, 'r') as f:
                self.role_permissions = json.load(f)
        except FileNotFoundError:
            # Default permissions - mirrors your current implementation
            self.role_permissions = {
                'developer': ['*'],  # All permissions
                'organization_owner': [
                    '*',
                    'organization.manage_users',
                    'organization.manage_settings', 
                    'organization.view_billing'
                ],
                'maker': [
                    'alerts.*',
                    'batch_rules.*', 
                    'recipe_builder.*',
                    'inventory.view',
                    'inventory.edit',
                    'inventory.adjust',
                    'products.view',
                    'products.edit',
                    'products.create',
                    'batches.view',
                    'batches.create',
                    'batches.edit',
                    'batches.finish',
                    'batches.cancel',
                    'recipes.view',
                    'recipes.edit',
                    'recipes.create',
                    'dashboard.view',
                    'settings.view',
                    'settings.edit',
                    'tags.manage',
                    'timers.manage'
                ],
                'manager': [
                    'alerts.*',
                    'batch_rules.*', 
                    'recipe_builder.*',
                    'inventory.view',
                    'inventory.edit',
                    'inventory.adjust',
                    'products.view',
                    'products.edit',
                    'products.create',
                    'batches.view',
                    'batches.create',
                    'batches.edit',
                    'batches.finish',
                    'batches.cancel',
                    'recipes.view',
                    'recipes.edit',
                    'recipes.create',
                    'dashboard.view',
                    'settings.view',
                    'settings.edit',
                    'tags.manage',
                    'timers.manage'
                ],
                'operator': [
                    'alerts.show_timer_alerts',
                    'alerts.show_batch_alerts', 
                    'batch_rules.require_timer_completion',
                    'batches.view',
                    'batches.create',
                    'batches.finish',
                    'recipes.view',
                    'inventory.view',
                    'dashboard.view',
                    'timers.view',
                    'timers.start',
                    'timers.stop'
                ]
            }
            self._save_permissions()

    def _save_permissions(self):
        """Save permissions to file"""
        with open(self.permissions_file, 'w') as f:
            json.dump(self.role_permissions, f, indent=2)

    def has_permission(self, user_role, permission):
        """Check if user role has specific permission"""
        if not user_role or user_role not in self.role_permissions:
            return False

        user_perms = self.role_permissions[user_role]

        # Check for wildcard permission
        if '*' in user_perms:
            return True

        # Check exact match
        if permission in user_perms:
            return True

        # Check wildcard patterns (e.g., 'alerts.*' matches 'alerts.show_timer_alerts')
        for perm in user_perms:
            if perm.endswith('.*'):
                prefix = perm[:-2]
                if permission.startswith(prefix + '.'):
                    return True

        return False

    def get_user_permissions(self, user_role):
        """Get all permissions for a user role"""
        return self.role_permissions.get(user_role, [])

    def has_subscription_feature(self, subscription_tier, feature):
        """Check if subscription tier has access to specific features"""
        feature_map = {
            'free': [
                'core_functionality',
                'basic_dashboard'
            ],
            'team': [
                'core_functionality',
                'basic_dashboard', 
                'team_management',
                'user_creation',
                'team_dashboard',
                'role_assignment'
            ],
            'enterprise': [
                'core_functionality',
                'basic_dashboard',
                'team_management', 
                'user_creation',
                'team_dashboard',
                'role_assignment',
                'advanced_analytics',
                'custom_integrations',
                'priority_support'
            ]
        }
        
        tier_features = feature_map.get(subscription_tier, [])
        return feature in tier_features

    def filter_data_by_scope(self, query, scope_context):
        """Apply scoping based on user, organization, or global access"""
        scope_type = scope_context.get('scope_type', 'user')
        user_id = scope_context.get('user_id')
        org_id = scope_context.get('organization_id')

        # Get the model from the query
        model = query.column_descriptions[0]['type'] if query.column_descriptions else None

        if scope_type == 'global':
            # Admin/system level - no filtering
            return query
        elif scope_type == 'organization' and org_id:
            # Organization level - filter by org
            if hasattr(model, 'organization_id'):
                return query.filter_by(organization_id=org_id)
            elif hasattr(model, 'created_by'):
                # Fallback: get all users in org, then filter by those users
                # This would need User.organization_id relationship
                return query.join(User).filter(User.organization_id == org_id)
        else:
            # User level - filter by user
            if hasattr(model, 'created_by'):
                return query.filter_by(created_by=user_id)

        return query

# Global permission manager instance
permission_manager = PermissionManager()

# Decorators for route protection
def require_permission(permission, scope_type='user'):
    """Decorator to require specific permission for route access with multi-tenant scoping

    Args:
        permission: Required permission string
        scope_type: 'user', 'organization', or 'global' - determines data scoping level
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                abort(401)

            user_role = getattr(current_user, 'role', 'maker')

            # Check permissions
            if not permission_manager.has_permission(user_role, permission):
                if request.is_json:
                    return jsonify({'error': 'Insufficient permissions'}), 403
                abort(403)

            # Apply scoping context
            kwargs['scope_context'] = {
                'user_id': current_user.id,
                'organization_id': getattr(current_user, 'organization_id', None),
                'scope_type': scope_type
            }

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_role(required_role):
    """Decorator to require specific role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)

            user_role = getattr(current_user, 'role', 'maker')

            if user_role != required_role and user_role != 'developer':
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def user_scoped_query(model_class):
    """Apply user-based scoping to database queries"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Inject user scoping logic into the function
            query = model_class.query
            if hasattr(model_class, 'created_by'):
                query = query.filter_by(created_by=current_user.id)
            kwargs['scoped_query'] = query
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Template function for permission checking
def has_permission(permission):
    """Template function to check permissions in Jinja2 templates"""
    if not current_user.is_authenticated:
        return False
    user_role = getattr(current_user, 'role', 'maker')
    return permission_manager.has_permission(user_role, permission)

# Template function for role checking  
def has_role(role):
    """Template function to check user role in Jinja2 templates"""
    if not current_user.is_authenticated:
        return False
    user_role = getattr(current_user, 'role', 'organization_owner')
    return user_role == role or user_role == 'developer'

# Template function for subscription feature checking
def has_subscription_feature(feature):
    """Template function to check subscription features in Jinja2 templates"""
    if not current_user.is_authenticated:
        return False
    
    subscription_tier = getattr(current_user.organization, 'subscription_tier', 'free')
    return permission_manager.has_subscription_feature(subscription_tier, feature)

# Template function for organization ownership checking
def is_organization_owner():
    """Template function to check if user is organization owner"""
    if not current_user.is_authenticated:
        return False
    return getattr(current_user, 'is_owner', False)