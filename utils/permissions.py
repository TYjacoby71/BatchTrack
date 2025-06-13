
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
                'admin': ['*'],  # All permissions
                'manager': [
                    'alerts.*',
                    'batch_rules.*', 
                    'recipe_builder.*',
                    'inventory.view',
                    'inventory.edit',
                    'products.view',
                    'products.edit',
                    'batches.view',
                    'batches.create',
                    'batches.edit',
                    'recipes.view',
                    'recipes.edit',
                    'dashboard.view'
                ],
                'operator': [
                    'alerts.show_timer_alerts',
                    'alerts.show_batch_alerts', 
                    'batch_rules.require_timer_completion',
                    'batches.view',
                    'batches.create',
                    'recipes.view',
                    'inventory.view',
                    'dashboard.view'
                ],
                'viewer': [
                    'alerts.show_expiration_alerts',
                    'dashboard.view',
                    'batches.view',
                    'recipes.view',
                    'inventory.view'
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
    
    def filter_data_by_user(self, query, user_id=None):
        """Apply user-based filtering for multi-tenancy"""
        if not user_id:
            user_id = current_user.id if current_user.is_authenticated else None
            
        # For now, we'll implement basic user filtering
        # You can expand this based on your tenancy model
        if hasattr(query.column_descriptions[0]['type'], 'created_by'):
            return query.filter_by(created_by=user_id)
        return query

# Global permission manager instance
permission_manager = PermissionManager()

# Decorators for route protection
def require_permission(permission):
    """Decorator to require specific permission for route access"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                abort(401)
            
            user_role = getattr(current_user, 'role', 'viewer')
            
            if not permission_manager.has_permission(user_role, permission):
                if request.is_json:
                    return jsonify({'error': 'Insufficient permissions'}), 403
                abort(403)
                
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
                
            user_role = getattr(current_user, 'role', 'viewer')
            
            if user_role != required_role and user_role != 'admin':
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
    user_role = getattr(current_user, 'role', 'viewer')
    return permission_manager.has_permission(user_role, permission)

# Template function for role checking  
def has_role(role):
    """Template function to check user role in Jinja2 templates"""
    if not current_user.is_authenticated:
        return False
    user_role = getattr(current_user, 'role', 'viewer')
    return user_role == role or user_role == 'admin'
