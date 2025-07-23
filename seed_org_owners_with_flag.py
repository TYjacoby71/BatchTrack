
#!/usr/bin/env python3
"""Seed organization owners with proper flag and role"""

from app.models import User, Role, UserRoleAssignment
from app.extensions import db
from app import create_app

def seed_org_owners_with_flag():
    """Set organization owner flags and assign roles"""
    
    app = create_app()
    with app.app_context():
        print("=== Setting Organization Owner Flags and Roles ===")
        
        # Get the organization owner system role
        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        
        if not org_owner_role:
            print("❌ Organization owner system role not found!")
            return False
        
        print(f"✅ Found organization owner role with {len(org_owner_role.permissions)} permissions")
        
        # Users who should be organization owners (one per organization)
        owner_usernames = ['admin', 'test1', 'test2', 'test3']
        
        print(f"\nSetting organization owner flag for: {owner_usernames}")
        
        # First, clear all existing organization owner flags
        all_users = User.query.filter(User.user_type == 'customer').all()
        for user in all_users:
            user.is_organization_owner = False
        
        print(f"✅ Cleared organization owner flags for all {len(all_users)} customer users")
        
        # Get all organizations to track which ones get owners
        organizations = {}
        
        # Set flags for specified users (one owner per organization)
        updated_count = 0
        assigned_count = 0
        
        for username in owner_usernames:
            user = User.query.filter_by(username=username).first()
            
            if user:
                if user.user_type == 'customer' and user.organization_id:
                    # Check if this organization already has an owner
                    if user.organization_id in organizations:
                        print(f"  ⚠️  Organization {user.organization_id} already has owner: {organizations[user.organization_id]}")
                        print(f"      Skipping user: {username}")
                        continue
                    
                    # Set the organization owner flag
                    user.is_organization_owner = True
                    organizations[user.organization_id] = username
                    updated_count += 1
                    print(f"  ✅ Set organization owner flag for: {username} (org_id: {user.organization_id})")
                    
                    # Check if user already has organization owner role
                    has_org_owner_role = any(
                        assignment.is_active and 
                        assignment.role_id == org_owner_role.id
                        for assignment in user.role_assignments
                    )
                    
                    if not has_org_owner_role:
                        user.assign_role(org_owner_role)
                        assigned_count += 1
                        print(f"  ✅ Assigned organization owner role to: {username}")
                    else:
                        print(f"  ✅ User {username} already has organization owner role")
                        
                elif user.user_type == 'developer':
                    print(f"  ⚠️  Skipping developer user: {username}")
                elif not user.organization_id:
                    print(f"  ⚠️  User {username} has no organization - skipping")
                    
            else:
                print(f"  ❌ User not found: {username}")
        
        db.session.commit()
        
        print(f"\n✅ Updated organization owner flags for {updated_count} users")
        print(f"✅ Assigned organization owner roles to {assigned_count} users")
        print(f"✅ Organizations with owners: {len(organizations)}")
        
        # Verify the results
        print("\n=== Verification ===")
        flagged_users = User.query.filter_by(is_organization_owner=True).all()
        
        for user in flagged_users:
            has_role = any(
                assignment.is_active and assignment.role_id == org_owner_role.id
                for assignment in user.role_assignments
            )
            print(f"👤 {user.username}: Flag=True, Role={'✅ Yes' if has_role else '❌ No'}")
        
        print("=== Seeding Complete ===")
        return True

if __name__ == '__main__':
    seed_org_owners_with_flag()
