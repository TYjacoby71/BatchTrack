
from ..extensions import db
from ..models import Role, Permission, role_permission

def seed_permissions():
    """Seed permissions from the existing permissions.json structure"""
    permissions_data = [
        # Developer permissions
        {'name': 'dev.dashboard', 'description': 'Access developer dashboard', 'category': 'developer'},
        {'name': 'dev.system_admin', 'description': 'System administration', 'category': 'developer'},
        {'name': 'dev.all_organizations', 'description': 'Access all organizations', 'category': 'developer'},
        
        # Organization permissions
        {'name': 'organization.manage_users', 'description': 'Manage organization users', 'category': 'organization'},
        {'name': 'organization.manage_settings', 'description': 'Manage organization settings', 'category': 'organization'},
        {'name': 'organization.view_billing', 'description': 'View billing information', 'category': 'organization'},
        
        # Alert permissions
        {'name': 'alerts.show_timer_alerts', 'description': 'Show timer alerts', 'category': 'alerts'},
        {'name': 'alerts.show_batch_alerts', 'description': 'Show batch alerts', 'category': 'alerts'},
        {'name': 'alerts.show_expiration_alerts', 'description': 'Show expiration alerts', 'category': 'alerts'},
        {'name': 'alerts.show_low_stock_alerts', 'description': 'Show low stock alerts', 'category': 'alerts'},
        {'name': 'alerts.max_dashboard_alerts', 'description': 'Configure max dashboard alerts', 'category': 'alerts'},
        
        # Batch permissions
        {'name': 'batches.view', 'description': 'View batches', 'category': 'batches'},
        {'name': 'batches.create', 'description': 'Create batches', 'category': 'batches'},
        {'name': 'batches.edit', 'description': 'Edit batches', 'category': 'batches'},
        {'name': 'batches.finish', 'description': 'Finish batches', 'category': 'batches'},
        {'name': 'batches.cancel', 'description': 'Cancel batches', 'category': 'batches'},
        
        # Inventory permissions
        {'name': 'inventory.view', 'description': 'View inventory', 'category': 'inventory'},
        {'name': 'inventory.edit', 'description': 'Edit inventory', 'category': 'inventory'},
        {'name': 'inventory.adjust', 'description': 'Adjust inventory', 'category': 'inventory'},
        
        # Product permissions
        {'name': 'products.view', 'description': 'View products', 'category': 'products'},
        {'name': 'products.edit', 'description': 'Edit products', 'category': 'products'},
        {'name': 'products.create', 'description': 'Create products', 'category': 'products'},
        
        # Recipe permissions
        {'name': 'recipes.view', 'description': 'View recipes', 'category': 'recipes'},
        {'name': 'recipes.edit', 'description': 'Edit recipes', 'category': 'recipes'},
        {'name': 'recipes.create', 'description': 'Create recipes', 'category': 'recipes'},
        
        # Settings permissions
        {'name': 'settings.view', 'description': 'View settings', 'category': 'settings'},
        {'name': 'settings.edit', 'description': 'Edit settings', 'category': 'settings'},
        
        # Dashboard permissions
        {'name': 'dashboard.view', 'description': 'View dashboard', 'category': 'dashboard'},
        
        # Timer permissions
        {'name': 'timers.view', 'description': 'View timers', 'category': 'timers'},
        {'name': 'timers.start', 'description': 'Start timers', 'category': 'timers'},
        {'name': 'timers.stop', 'description': 'Stop timers', 'category': 'timers'},
        {'name': 'timers.manage', 'description': 'Manage timers', 'category': 'timers'},
        
        # Tags permissions
        {'name': 'tags.manage', 'description': 'Manage tags', 'category': 'tags'},
    ]
    
    for perm_data in permissions_data:
        existing = Permission.query.filter_by(name=perm_data['name']).first()
        if not existing:
            permission = Permission(**perm_data)
            db.session.add(permission)
    
    db.session.commit()

def seed_roles():
    """Seed roles based on existing role structure"""
    roles_data = [
        {
            'name': 'developer',
            'description': 'Full system access and development privileges',
            'permissions': ['dev.dashboard', 'dev.system_admin', 'dev.all_organizations']
        },
        {
            'name': 'organization_owner',
            'description': 'Full access within organization',
            'permissions': [
                'organization.manage_users', 'organization.manage_settings', 'organization.view_billing',
                'alerts.show_timer_alerts', 'alerts.show_batch_alerts', 'alerts.show_expiration_alerts',
                'alerts.show_low_stock_alerts', 'alerts.max_dashboard_alerts',
                'batches.view', 'batches.create', 'batches.edit', 'batches.finish', 'batches.cancel',
                'inventory.view', 'inventory.edit', 'inventory.adjust',
                'products.view', 'products.edit', 'products.create',
                'recipes.view', 'recipes.edit', 'recipes.create',
                'settings.view', 'settings.edit', 'dashboard.view',
                'timers.view', 'timers.start', 'timers.stop', 'timers.manage',
                'tags.manage'
            ]
        },
        {
            'name': 'manager',
            'description': 'Management access to operations',
            'permissions': [
                'alerts.show_timer_alerts', 'alerts.show_batch_alerts', 'alerts.show_expiration_alerts',
                'alerts.show_low_stock_alerts',
                'batches.view', 'batches.create', 'batches.edit', 'batches.finish', 'batches.cancel',
                'inventory.view', 'inventory.edit', 'inventory.adjust',
                'products.view', 'products.edit', 'products.create',
                'recipes.view', 'recipes.edit', 'recipes.create',
                'settings.view', 'settings.edit', 'dashboard.view',
                'timers.view', 'timers.start', 'timers.stop', 'timers.manage',
                'tags.manage'
            ]
        },
        {
            'name': 'operator',
            'description': 'Basic operational access',
            'permissions': [
                'alerts.show_timer_alerts', 'alerts.show_batch_alerts',
                'batches.view', 'batches.create', 'batches.finish',
                'recipes.view', 'inventory.view', 'dashboard.view',
                'timers.view', 'timers.start', 'timers.stop'
            ]
        }
    ]
    
    for role_data in roles_data:
        existing_role = Role.query.filter_by(name=role_data['name']).first()
        if not existing_role:
            role = Role(name=role_data['name'], description=role_data['description'])
            db.session.add(role)
            db.session.commit()
            
            # Add permissions to role
            for perm_name in role_data['permissions']:
                permission = Permission.query.filter_by(name=perm_name).first()
                if permission:
                    role.permissions.append(permission)
            
            db.session.commit()

def seed_roles_and_permissions():
    """Seed both roles and permissions"""
    seed_permissions()
    seed_roles()
    print("Roles and permissions seeded successfully!")
