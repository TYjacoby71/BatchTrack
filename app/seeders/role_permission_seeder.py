from ..models import Role, Permission, db, role_permission
from ..extensions import db as database
from ..utils.permission_management import update_organization_owner_permissions as update_org_owner_perms

def seed_permissions():
    """Seed all permissions using consolidated permissions system"""
    print("⚠️  Using legacy seeder. Please run 'python seed_consolidated_permissions.py' instead.")
    print("This will use the new consolidated permissions structure with better organization.")
    
    # Fallback to basic permissions if consolidated file doesn't exist
    import os
    if not os.path.exists('consolidated_permissions.json'):
        print("Consolidated permissions file not found. Creating basic permissions...")
        
        basic_permissions = [
            {'name': 'dashboard.view', 'description': 'View main dashboard with production overview and alerts', 'category': 'dashboard', 'tier': 'free'},
            {'name': 'inventory.view', 'description': 'View all inventory items and stock levels', 'category': 'inventory_management', 'tier': 'free'},
            {'name': 'inventory.edit', 'description': 'Modify inventory item details and specifications', 'category': 'inventory_management', 'tier': 'free'},
            {'name': 'inventory.adjust', 'description': 'Manually adjust inventory quantities and record changes', 'category': 'inventory_management', 'tier': 'free'},
            {'name': 'recipes.view', 'description': 'Access recipe details and ingredient lists', 'category': 'recipe_management', 'tier': 'free'},
            {'name': 'recipes.create', 'description': 'Create new recipes with ingredients and instructions', 'category': 'recipe_management', 'tier': 'free'},
            {'name': 'recipes.edit', 'description': 'Modify existing recipes and update ingredients', 'category': 'recipe_management', 'tier': 'free'},
            {'name': 'batches.view', 'description': 'Access batch details and production history', 'category': 'batch_production', 'tier': 'free'},
            {'name': 'batches.create', 'description': 'Start new production batches from recipes', 'category': 'batch_production', 'tier': 'free'},
            {'name': 'batches.edit', 'description': 'Modify batch information and notes', 'category': 'batch_production', 'tier': 'free'},
            {'name': 'batches.finish', 'description': 'Complete production batches and add finished goods', 'category': 'batch_production', 'tier': 'free'},
            {'name': 'products.view', 'description': 'Access product catalog and SKU details', 'category': 'product_management', 'tier': 'free'},
            {'name': 'products.create', 'description': 'Add new products to catalog with SKUs', 'category': 'product_management', 'tier': 'free'},
            {'name': 'products.edit', 'description': 'Modify product details and specifications', 'category': 'product_management', 'tier': 'free'},
        ]
        
        for perm_data in basic_permissions:
            permission = Permission.query.filter_by(name=perm_data['name']).first()
            if not permission:
                permission = Permission(
                    name=perm_data['name'],
                    description=perm_data['description'],
                    category=perm_data['category'],
                    required_subscription_tier=perm_data['tier']
                )
                db.session.add(permission)
        
        db.session.commit()
        print(f"✅ Created {len(basic_permissions)} basic permissions")
    else:
        print("✅ Consolidated permissions file found. Run consolidated seeder for full permissions.")

def seed_system_roles():
    """Seed system roles that are available to all organizations"""
    system_roles = [
        {
            'name': 'organization_owner',
            'description': 'Organization owner with all permissions available to subscription tier.',
            'permissions': 'all',  # Special marker for all permissions
            'is_system_role': True
        },
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
            try:
                db.session.flush()  # Get the ID
            except Exception as e:
                # If there's a constraint error, try to find an existing role
                db.session.rollback()
                role = Role.query.filter_by(name=role_data['name']).first()
                if not role:
                    print(f"❌ Could not create or find role '{role_data['name']}': {e}")
                    continue
                else:
                    # Update existing role to be a system role
                    role.is_system_role = True
                    role.description = role_data['description']
                    role.organization_id = None
        else:
            role.description = role_data['description']

        # Clear existing permissions
        role.permissions.clear()

        # Add permissions
        if role_data['permissions'] == 'all':
            # Organization owner gets all permissions
            all_permissions = Permission.query.filter_by().all()
            role.permissions = all_permissions
            print(f"✅ Assigned all {len(all_permissions)} permissions to {role.name}")
        else:
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
    # Update organization owner role with any new permissions
    update_org_owner_perms()
    print("✅ Roles and permissions seeded successfully!")

if __name__ == "__main__":
    from .. import create_app
    app = create_app()
    with app.app_context():
        seed_roles_and_permissions()