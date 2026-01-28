#!/usr/bin/env python3
"""Seed the consolidated permissions system"""

import json
import os
from flask import current_app
from ..models import Permission, DeveloperPermission, Role, db
from ..models.developer_role import DeveloperRole

def load_consolidated_permissions():
    """Load permissions from the consolidated JSON file"""
    # Look for the JSON file in the seeders directory
    json_path = os.path.join(os.path.dirname(__file__), 'consolidated_permissions.json')
    
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Consolidated permissions file not found at: {json_path}")
    
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Validate the structure
        if 'organization_permissions' not in data or 'developer_permissions' not in data:
            raise ValueError("Invalid permissions file structure - missing required sections")
        
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in consolidated permissions file: {e}")

def seed_organization_permissions():
    """Seed organization permissions from consolidated file"""
    try:
        data = load_consolidated_permissions()
        org_permissions = data['organization_permissions']

        print("🔧 Seeding organization permissions...")
        permissions_created = 0
        permissions_updated = 0

        for category_key, category_data in org_permissions.items():
            if not isinstance(category_data, dict) or 'permissions' not in category_data:
                print(f"⚠️  Skipping invalid category: {category_key}")
                continue
                
            permissions = category_data['permissions']

            for perm_data in permissions:
                if not isinstance(perm_data, dict) or 'name' not in perm_data:
                    continue
                    
                existing = Permission.query.filter_by(name=perm_data['name']).first()

                if existing:
                    existing.description = perm_data.get('description', perm_data['name'])
                    existing.category = category_key
                    permissions_updated += 1
                else:
                    new_perm = Permission(
                        name=perm_data['name'],
                        description=perm_data.get('description', perm_data['name']),
                        category=category_key
                    )
                    db.session.add(new_perm)
                    permissions_created += 1

        db.session.commit()
        print(f"   ✅ Organization permissions: {permissions_created} created, {permissions_updated} updated")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error seeding organization permissions: {e}")
        raise

def seed_developer_permissions():
    """Seed developer permissions from consolidated file"""
    try:
        data = load_consolidated_permissions()
        dev_permissions = data['developer_permissions']

        print("🔧 Seeding developer permissions...")
        permissions_created = 0
        permissions_updated = 0

        for category_key, category_data in dev_permissions.items():
            if not isinstance(category_data, dict) or 'permissions' not in category_data:
                print(f"⚠️  Skipping invalid developer category: {category_key}")
                continue
                
            permissions = category_data['permissions']

            for perm_data in permissions:
                if not isinstance(perm_data, dict) or 'name' not in perm_data:
                    continue
                    
                existing = DeveloperPermission.query.filter_by(name=perm_data['name']).first()

                if existing:
                    existing.description = perm_data.get('description', perm_data['name'])
                    existing.category = category_key
                    permissions_updated += 1
                else:
                    new_perm = DeveloperPermission(
                        name=perm_data['name'],
                        description=perm_data.get('description', perm_data['name']),
                        category=category_key
                    )
                    db.session.add(new_perm)
                    permissions_created += 1

        db.session.commit()
        print(f"   ✅ Developer permissions: {permissions_created} created, {permissions_updated} updated")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error seeding developer permissions: {e}")
        raise

def seed_developer_roles():
    """Create developer roles and assign permissions"""
    print("🔧 Seeding developer roles...")

    # System Admin Role - full system access
    system_admin_role = DeveloperRole.query.filter_by(name='system_admin').first()
    if not system_admin_role:
        system_admin_role = DeveloperRole(
            name='system_admin',
            description='Full system administration access across all organizations',
            category='admin',
            is_active=True
        )
        db.session.add(system_admin_role)
        db.session.flush()

    all_dev_permissions = DeveloperPermission.query.filter_by(is_active=True).all()
    system_admin_role.permissions = all_dev_permissions

    # Developer Role - limited development access
    developer_role = DeveloperRole.query.filter_by(name='developer').first()
    if not developer_role:
        developer_role = DeveloperRole(
            name='developer',
            description='Basic developer access for debugging and development',
            category='developer',
            is_active=True
        )
        db.session.add(developer_role)
        db.session.flush()

    dev_permissions = DeveloperPermission.query.filter(
        DeveloperPermission.name.in_([
            'dev.dashboard',
            'dev.debug_mode',
            'dev.access_logs',
        ])
    ).all()
    developer_role.permissions = dev_permissions

    # Support Role - read-only access for support staff
    support_role = DeveloperRole.query.filter_by(name='support').first()
    if not support_role:
        support_role = DeveloperRole(
            name='support',
            description='Read-only access for customer support',
            category='support',
            is_active=True
        )
        db.session.add(support_role)
        db.session.flush()

    support_permissions = DeveloperPermission.query.filter(
        DeveloperPermission.name.in_(['dev.dashboard', 'dev.access_logs'])
    ).all()
    support_role.permissions = support_permissions

    db.session.commit()
    print(f"   ✅ Developer roles: 3 roles created/updated")

def update_organization_owner_role():
    """Update organization owner role with necessary permissions"""
    org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()

    if org_owner_role:
        # Always ensure organization owner role has all customer-facing permissions
        # Get all customer-facing permissions (not just app and organization categories)
        customer_permissions = Permission.query.filter(
            Permission.is_active == True
        ).all()

        # Update permissions to role
        org_owner_role.permissions = customer_permissions
        db.session.commit()

        print(f"✅ Updated organization owner role with {len(customer_permissions)} permissions")
    else:
        print("⚠️  organization_owner role not found - it should be created by seed_organization_roles()")

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

    # Find and remove old organization permissions (and associations)
    old_org_perms = Permission.query.filter(~Permission.name.in_(org_perm_names)).all()
    for perm in old_org_perms:
        perm.roles = []
        try:
            for tier in perm.tiers.all():
                perm.tiers.remove(tier)
        except Exception:
            pass
        db.session.delete(perm)
        print(f"Removed old organization permission: {perm.name}")

    # Remove legacy app.* developer permissions outright
    legacy_dev_perms = DeveloperPermission.query.filter(
        DeveloperPermission.name.like("app.%")
    ).all()
    for perm in legacy_dev_perms:
        perm.developer_roles = []
        db.session.delete(perm)
        print(f"Removed legacy developer permission: {perm.name}")

    # Find and remove old developer permissions (keep shared org names too)
    allowed_dev_names = dev_perm_names.union(org_perm_names)
    old_dev_perms = DeveloperPermission.query.filter(~DeveloperPermission.name.in_(allowed_dev_names)).all()
    for perm in old_dev_perms:
        perm.developer_roles = []
        db.session.delete(perm)
        print(f"Removed old developer permission: {perm.name}")

    db.session.commit()
    print("✅ Cleaned up old permissions")

def seed_organization_roles():
    """Seed initial organization system roles (these can be used by any organization)"""
    print("🔧 Seeding organization system roles...")

    org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
    if not org_owner_role:
        org_owner_role = Role(
            name='organization_owner',
            description='Organization owner with full access to their organization',
            is_system_role=True,
            is_active=True,
            organization_id=None
        )
        db.session.add(org_owner_role)

        customer_permissions = Permission.query.filter(
            Permission.category.in_(['app', 'organization'])
        ).all()
        org_owner_role.permissions = customer_permissions

        db.session.commit()

    print(f"   ✅ Organization system roles: 1 role created/updated")

def seed_consolidated_permissions():
    """Main seeder function"""
    if not current_app:
        raise RuntimeError("seed_consolidated_permissions() must be called within Flask application context")

    print("🔧 Seeding consolidated permissions...")

    seed_organization_permissions()
    seed_developer_permissions()
    seed_developer_roles()
    seed_organization_roles()
    update_organization_owner_role()
    cleanup_old_permissions()

    org_count = Permission.query.filter_by(is_active=True).count()
    dev_count = DeveloperPermission.query.filter_by(is_active=True).count()
    print(f"   ✅ Permissions complete: {org_count} org permissions, {dev_count} dev permissions")

