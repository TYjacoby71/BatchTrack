
#!/usr/bin/env python3
"""Seed the consolidated permissions system"""

import json
import os
from flask import current_app
from ..models import Permission, DeveloperPermission, Role, db

def load_consolidated_permissions():
    """Load permissions from the consolidated JSON file"""
    # Look for the JSON file in the root directory
    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'consolidated_permissions.json')
    with open(json_path, 'r') as f:
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
                existing.required_subscription_tier = perm_data['required_tier']
                print(f"  Updated: {perm_data['name']}")
            else:
                # Create new permission
                new_perm = Permission(
                    name=perm_data['name'],
                    description=perm_data['description'],
                    category=category_key,
                    required_subscription_tier=perm_data['required_tier']
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
    """Update organization owner role with necessary permissions"""
    org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
    
    if not org_owner_role:
        # Create organization owner role if it doesn't exist
        org_owner_role = Role(
            name='organization_owner',
            description='Organization owner with full access to their organization',
            is_system_role=True,
            is_active=True
        )
        db.session.add(org_owner_role)
        db.session.flush()
    
    # Get all organization management permissions
    org_management_perms = Permission.query.filter(
        Permission.category.in_(['organization_management', 'user_management'])
    ).all()
    
    # Add permissions to role
    org_owner_role.permissions = org_management_perms
    db.session.commit()
    
    print(f"✅ Updated organization owner role with {len(org_management_perms)} permissions")

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

def seed_consolidated_permissions():
    """Main seeder function"""
    # Ensure we're in an application context
    if not current_app:
        raise RuntimeError("seed_consolidated_permissions() must be called within Flask application context")
    
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
