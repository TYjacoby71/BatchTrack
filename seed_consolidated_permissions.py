
#!/usr/bin/env python3
"""Seed the consolidated permissions system"""

import json
from app import create_app
from app.models import Permission, DeveloperPermission, Role, db
from app.extensions import db as database

def load_consolidated_permissions():
    """Load permissions from the consolidated JSON file"""
    with open('consolidated_permissions.json', 'r') as f:
        return json.load(f)

def seed_organization_permissions():
    """Seed organization permissions from consolidated file"""
    data = load_consolidated_permissions()
    org_permissions = data['organization_permissions']
    
    print("Seeding organization permissions...")
    
    for category_key, category_data in org_permissions.items():
        category_name = category_data['description']
        permissions = category_data['permissions']
        
        print(f"Processing category: {category_name}")
        
        for perm_data in permissions:
            # Check if permission already exists
            existing = Permission.query.filter_by(name=perm_data['name']).first()
            
            if existing:
                # Update existing permission
                existing.description = perm_data['description']
                existing.category = category_key
                # Remove required_subscription_tier as permissions are now subscription-agnostic
                # No tier assignment needed for individual permissions
                print(f"  Updated: {perm_data['name']}")
            else:
                # Create new permission
                new_perm = Permission(
                    name=perm_data['name'],
                    description=perm_data['description'],
                    category=category_key,
                    # No tier assignment needed for individual permissions
                )
                db.session.add(new_perm)
                print(f"  Created: {perm_data['name']}")
    
    db.session.commit()
    print("✅ Organization permissions seeded successfully!")

def seed_developer_permissions():
    """Seed developer permissions from consolidated file"""
    data = load_consolidated_permissions()
    dev_permissions = data['developer_permissions']
    
    print("Seeding developer permissions...")
    
    for category_key, category_data in dev_permissions.items():
        category_name = category_data['description']
        permissions = category_data['permissions']
        
        print(f"Processing category: {category_name}")
        
        for perm_data in permissions:
            # Check if permission already exists
            existing = DeveloperPermission.query.filter_by(name=perm_data['name']).first()
            
            if existing:
                # Update existing permission
                existing.description = perm_data['description']
                existing.category = category_key
                print(f"  Updated: {perm_data['name']}")
            else:
                # Create new permission
                new_perm = DeveloperPermission(
                    name=perm_data['name'],
                    description=perm_data['description'],
                    category=category_key
                )
                db.session.add(new_perm)
                print(f"  Created: {perm_data['name']}")
    
    db.session.commit()
    print("✅ Developer permissions seeded successfully!")

def update_organization_owner_role():
    """Update organization owner role to have all organization permissions"""
    print("Updating organization owner role...")
    
    # Find the organization owner role
    owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
    
    if owner_role:
        # Clear existing permissions
        owner_role.permissions.clear()
        
        # Add all organization permissions
        all_org_permissions = Permission.query.filter_by(is_active=True).all()
        owner_role.permissions = all_org_permissions
        
        db.session.commit()
        print(f"✅ Updated organization owner role with {len(all_org_permissions)} permissions")
    else:
        print("❌ Organization owner role not found")

def cleanup_old_permissions():
    """Remove permissions that are no longer in the consolidated file"""
    data = load_consolidated_permissions()
    
    # Get all permission names from consolidated file
    org_perm_names = set()
    for category_data in data['organization_permissions'].values():
        for perm in category_data['permissions']:
            org_perm_names.add(perm['name'])
    
    dev_perm_names = set()
    for category_data in data['developer_permissions'].values():
        for perm in category_data['permissions']:
            dev_perm_names.add(perm['name'])
    
    # Find and deactivate old organization permissions
    old_org_perms = Permission.query.filter(~Permission.name.in_(org_perm_names)).all()
    for perm in old_org_perms:
        perm.is_active = False
        print(f"Deactivated old organization permission: {perm.name}")
    
    # Find and deactivate old developer permissions
    old_dev_perms = DeveloperPermission.query.filter(~DeveloperPermission.name.in_(dev_perm_names)).all()
    for perm in old_dev_perms:
        perm.is_active = False
        print(f"Deactivated old developer permission: {perm.name}")
    
    db.session.commit()
    print("✅ Cleaned up old permissions")

def main():
    """Main seeder function"""
    app = create_app()
    
    with app.app_context():
        print("=== Seeding Consolidated Permissions System ===")
        
        # Seed permissions
        seed_organization_permissions()
        seed_developer_permissions()
        
        # Update roles
        update_organization_owner_role()
        
        # Cleanup old permissions
        cleanup_old_permissions()
        
        print("✅ Consolidated permissions system seeded successfully!")
        
        # Display summary
        org_count = Permission.query.filter_by(is_active=True).count()
        dev_count = DeveloperPermission.query.filter_by(is_active=True).count()
        
        print(f"\n📊 Summary:")
        print(f"Organization permissions: {org_count}")
        print(f"Developer permissions: {dev_count}")

if __name__ == "__main__":
    main()
