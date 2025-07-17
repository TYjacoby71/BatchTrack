from ..models import Role, Permission, db, role_permission
from ..extensions import db as database

def seed_permissions():
    """Seed all permissions with their subscription tier requirements"""
    permissions_data = [
        # Dashboard permissions
        {'name': 'dashboard.view', 'description': 'View dashboard', 'category': 'dashboard', 'tier': 'free'},

        # Alert permissions
        {'name': 'alerts.view', 'description': 'View alerts', 'category': 'alerts', 'tier': 'free'},
        {'name': 'alerts.manage', 'description': 'Manage alert settings', 'category': 'alerts', 'tier': 'team'},

        # Batch permissions
        {'name': 'batches.view', 'description': 'View batches', 'category': 'batches', 'tier': 'free'},
        {'name': 'batches.create', 'description': 'Create batches', 'category': 'batches', 'tier': 'free'},
        {'name': 'batches.edit', 'description': 'Edit batches', 'category': 'batches', 'tier': 'free'},
        {'name': 'batches.finish', 'description': 'Finish batches', 'category': 'batches', 'tier': 'free'},
        {'name': 'batches.cancel', 'description': 'Cancel batches', 'tier': 'free'},

        # Inventory permissions
        {'name': 'inventory.view', 'description': 'View inventory', 'category': 'inventory', 'tier': 'free'},
        {'name': 'inventory.edit', 'description': 'Edit inventory', 'category': 'inventory', 'tier': 'free'},
        {'name': 'inventory.adjust', 'description': 'Adjust inventory', 'category': 'inventory', 'tier': 'free'},
        {'name': 'inventory.reserve', 'description': 'Reserve inventory', 'category': 'inventory', 'tier': 'team'},
        {'name': 'inventory.delete', 'description': 'Delete inventory', 'category': 'inventory', 'tier': 'team'},

        # Product permissions
        {'name': 'products.view', 'description': 'View products', 'category': 'products', 'tier': 'free'},
        {'name': 'products.edit', 'description': 'Edit products', 'category': 'products', 'tier': 'free'},
        {'name': 'products.create', 'description': 'Create products', 'category': 'products', 'tier': 'free'},
        {'name': 'products.delete', 'description': 'Delete products', 'category': 'products', 'tier': 'team'},

        # Recipe permissions
        {'name': 'recipes.view', 'description': 'View recipes', 'category': 'recipes', 'tier': 'free'},
        {'name': 'recipes.create', 'description': 'Create recipes', 'category': 'recipes', 'tier': 'free'},
        {'name': 'recipes.edit', 'description': 'Edit recipes', 'category': 'recipes', 'tier': 'free'},
        {'name': 'recipes.delete', 'description': 'Delete recipes', 'category': 'recipes', 'tier': 'team'},

        # Organization permissions
        {'name': 'organization.view', 'description': 'View organization settings', 'category': 'organization', 'tier': 'team'},
        {'name': 'organization.edit', 'description': 'Edit organization settings', 'category': 'organization', 'tier': 'team'},
        {'name': 'organization.manage_users', 'description': 'Manage organization users', 'category': 'organization', 'tier': 'team'},
        {'name': 'organization.manage_roles', 'description': 'Manage organization roles', 'category': 'organization', 'tier': 'team'},
        {'name': 'organization.manage_billing', 'description': 'Manage billing', 'category': 'organization', 'tier': 'team'},

        # Reporting permissions
        {'name': 'reports.view', 'description': 'View reports', 'category': 'reports', 'tier': 'team'},
        {'name': 'reports.export', 'description': 'Export reports', 'category': 'reports', 'tier': 'team'},
        {'name': 'reports.advanced', 'description': 'Advanced reporting', 'category': 'reports', 'tier': 'enterprise'},

        # API permissions
        {'name': 'api.access', 'description': 'API access', 'category': 'api', 'tier': 'enterprise'},
        {'name': 'api.admin', 'description': 'API administration', 'category': 'api', 'tier': 'enterprise'},

        # System permissions
        {'name': 'system.admin', 'description': 'System administration', 'category': 'system', 'tier': 'enterprise'},
        {'name': 'system.debug', 'description': 'System debugging', 'category': 'system', 'tier': 'enterprise'},
    ]

    print("Seeding permissions...")
    for perm_data in permissions_data:
        permission = Permission.query.filter_by(name=perm_data['name']).first()
        if not permission:
            permission = Permission(
                name=perm_data['name'],
                description=perm_data['description'],
                category=perm_data['category'],
                required_subscription_tier=perm_data['tier']
            )
            db.session.add(permission)
        else:
            # Update existing permission
            permission.description = perm_data['description']
            permission.category = perm_data['category']
            permission.required_subscription_tier = perm_data['tier']

    db.session.commit()
    print(f"✅ Seeded {len(permissions_data)} permissions")

def seed_system_roles():
    """Seed system roles that are available to all organizations"""
    system_roles = [
        {
            'name': 'viewer',
            'description': 'Can view basic information',
            'permissions': ['dashboard.view', 'batches.view', 'inventory.view', 'products.view', 'recipes.view']
        },
        {
            'name': 'operator',
            'description': 'Basic operations role',
            'permissions': [
                'dashboard.view', 'batches.view', 'batches.create', 'batches.edit', 'batches.finish',
                'inventory.view', 'inventory.edit', 'inventory.adjust',
                'products.view', 'products.edit', 'products.create',
                'recipes.view', 'recipes.create', 'recipes.edit'
            ]
        },
        {
            'name': 'editor',
            'description': 'Can edit and create content',
            'permissions': [
                'dashboard.view', 'batches.view', 'batches.create', 'batches.edit', 'batches.finish',
                'inventory.view', 'inventory.edit', 'inventory.adjust',
                'products.view', 'products.edit', 'products.create',
                'recipes.view', 'recipes.create', 'recipes.edit'
            ]
        },
        {
            'name': 'manager',
            'description': 'Can manage operations and users',
            'permissions': [
                'dashboard.view', 'alerts.view', 'alerts.manage',
                'batches.view', 'batches.create', 'batches.edit', 'batches.finish', 'batches.cancel',
                'inventory.view', 'inventory.edit', 'inventory.adjust', 'inventory.reserve', 'inventory.delete',
                'products.view', 'products.edit', 'products.create', 'products.delete',
                'recipes.view', 'recipes.create', 'recipes.edit', 'recipes.delete',
                'organization.view', 'organization.manage_users', 'organization.manage_roles',
                'reports.view', 'reports.export'
            ]
        },
        {
            'name': 'organization_owner',
            'description': 'Organization owner with full access to organization management',
            'permissions': [
                'dashboard.view', 'alerts.view', 'alerts.manage',
                'batches.view', 'batches.create', 'batches.edit', 'batches.finish', 'batches.cancel',
                'inventory.view', 'inventory.edit', 'inventory.adjust', 'inventory.reserve', 'inventory.delete',
                'products.view', 'products.edit', 'products.create', 'products.delete',
                'recipes.view', 'recipes.create', 'recipes.edit', 'recipes.delete',
                'organization.view', 'organization.edit', 'organization.manage_users', 'organization.manage_roles', 'organization.manage_billing',
                'reports.view', 'reports.export', 'reports.advanced',
                'api.access', 'api.admin'
            ]
        },
        {
            'name': 'admin',
            'description': 'Full administrative access',
            'permissions': [
                'dashboard.view', 'alerts.view', 'alerts.manage',
                'batches.view', 'batches.create', 'batches.edit', 'batches.finish', 'batches.cancel',
                'inventory.view', 'inventory.edit', 'inventory.adjust', 'inventory.reserve', 'inventory.delete',
                'products.view', 'products.edit', 'products.create', 'products.delete',
                'recipes.view', 'recipes.create', 'recipes.edit', 'recipes.delete',
                'organization.view', 'organization.edit', 'organization.manage_users', 'organization.manage_roles', 'organization.manage_billing',
                'reports.view', 'reports.export', 'reports.advanced',
                'api.access', 'api.admin'
            ]
        },

    ]

    print("Seeding system roles...")
    # Create roles (developers don't use the role system - they have direct access)
    for role_data in system_roles:
        role = Role.query.filter_by(name=role_data['name'], is_system_role=True).first()
        if not role:
            role = Role(
                name=role_data['name'],
                description=role_data['description'],
                is_system_role=True,
                organization_id=None
            )
            db.session.add(role)
            db.session.flush()  # Get the ID
        else:
            role.description = role_data['description']

        # Clear existing permissions
        role.permissions.clear()

        # Add permissions
        for perm_name in role_data['permissions']:
            permission = Permission.query.filter_by(name=perm_name).first()
            if permission:
                role.permissions.append(permission)

    db.session.commit()
    print(f"✅ Seeded {len(system_roles)} system roles")

def seed_roles_and_permissions():
    """Main seeder function"""
    print("=== Seeding Roles and Permissions ===")
    seed_permissions()
    seed_system_roles()
    print("✅ Roles and permissions seeded successfully!")

if __name__ == "__main__":
    seed_roles_and_permissions()