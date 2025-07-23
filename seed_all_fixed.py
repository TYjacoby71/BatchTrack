
#!/usr/bin/env python3
"""Comprehensive seeder to fix all data and relationships"""

from app import create_app
from app.models import db, User, Organization, Role, UserRoleAssignment, Subscription
from app.seeders.consolidated_permission_seeder import seed_consolidated_permissions
from app.seeders.unit_seeder import seed_units
from app.seeders.ingredient_category_seeder import seed_categories
from datetime import datetime

def seed_all_fixed():
    """Seed all data and fix relationships"""
    app = create_app()
    
    with app.app_context():
        print("=== Starting Comprehensive Data Seeding ===")
        
        # 1. Seed permissions and roles first
        print("\n1. Seeding permissions and roles...")
        seed_consolidated_permissions()
        
        # 2. Seed units
        print("\n2. Seeding units...")
        seed_units()
        
        # 3. Seed categories  
        print("\n3. Seeding ingredient categories...")
        seed_categories()
        
        # 4. Fix organization subscriptions
        print("\n4. Creating/fixing organization subscriptions...")
        orgs = Organization.query.all()
        for org in orgs:
            if not org.subscription:
                # Determine tier based on org ID
                tier = 'exempt' if org.id == 1 else 'free'
                subscription = Subscription(
                    organization_id=org.id,
                    tier=tier,
                    status='active',
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    notes=f'Auto-created subscription for organization {org.id}'
                )
                db.session.add(subscription)
                print(f"  ✅ Created {tier} subscription for organization {org.id}")
            else:
                print(f"  ✅ Organization {org.id} already has subscription")
        
        db.session.commit()
        
        # 5. Fix organization owner flags and roles
        print("\n5. Setting organization owner flags and roles...")
        
        # Get the organization owner system role
        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        
        if not org_owner_role:
            print("❌ Organization owner system role not found!")
            return False
        
        print(f"✅ Found organization owner role with {len(org_owner_role.permissions)} permissions")
        
        # Users who should be organization owners
        owner_usernames = ['admin', 'test1', 'test2', 'test3']
        
        # First, clear all existing organization owner flags
        all_users = User.query.all()
        cleared_count = 0
        for user in all_users:
            if user.is_organization_owner:
                user._is_organization_owner = False
                cleared_count += 1
        
        print(f"✅ Cleared organization owner flags for {cleared_count} users")
        
        # Set flags and roles for specified users
        updated_count = 0
        assigned_count = 0
        
        for username in owner_usernames:
            user = User.query.filter_by(username=username).first()
            
            if user:
                print(f"\n  Processing user: {username}")
                
                # Change user_type to customer if it's organization_owner
                if user.user_type == 'organization_owner':
                    user.user_type = 'customer'
                    print(f"    ✅ Changed user type from organization_owner to customer")
                
                # Set the organization owner flag
                user._is_organization_owner = True
                updated_count += 1
                print(f"    ✅ Set organization owner flag")
                
                # Check if user already has organization owner role
                has_org_owner_role = any(
                    assignment.is_active and 
                    assignment.role_id == org_owner_role.id
                    for assignment in user.role_assignments
                )
                
                if not has_org_owner_role:
                    user.assign_role(org_owner_role)
                    assigned_count += 1
                    print(f"    ✅ Assigned organization owner role")
                else:
                    print(f"    ✅ User already has organization owner role")
                    
            else:
                print(f"  ❌ User not found: {username}")
        
        db.session.commit()
        
        print(f"\n✅ Updated organization owner flags for {updated_count} users")
        print(f"✅ Assigned organization owner roles to {assigned_count} users")
        
        # 6. Verify everything
        print("\n=== Final Verification ===")
        
        # Check subscriptions
        orgs_with_subs = Organization.query.all()
        print(f"Organizations: {len(orgs_with_subs)}")
        for org in orgs_with_subs:
            sub_status = "✅ Has subscription" if org.subscription else "❌ No subscription"
            print(f"  Org {org.id} ({org.name}): {sub_status}")
        
        # Check organization owners
        org_owners = User.query.filter_by(_is_organization_owner=True).all()
        print(f"\nOrganization owners: {len(org_owners)}")
        
        for user in org_owners:
            has_role = any(
                assignment.is_active and assignment.role_id == org_owner_role.id
                for assignment in user.role_assignments
            )
            print(f"  👤 {user.username}: Flag=True, Role={'✅ Yes' if has_role else '❌ No'}, Type={user.user_type}")
        
        print("\n=== Seeding Complete ===")
        return True

if __name__ == '__main__':
    seed_all_fixed()
