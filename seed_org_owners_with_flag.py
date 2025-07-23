
#!/usr/bin/env python3
"""Seed organization owner flags for existing users"""

from app.models import User, Role, UserRoleAssignment
from app.extensions import db
from app import create_app

def seed_organization_owners():
    """Seed organization owner flags and roles for specified users"""
    
    app = create_app()
    with app.app_context():
        print("=== Seeding Organization Owner Flags and Roles ===")
        
        # Get the organization owner system role
        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        
        if not org_owner_role:
            print("❌ Organization owner system role not found!")
            return False
        
        print(f"✅ Found organization owner role with {len(org_owner_role.permissions)} permissions")
        
        # Users who should be organization owners
        owner_usernames = ['admin', 'test1', 'test2', 'test3']
        
        print(f"\nSetting organization owner flag for: {owner_usernames}")
        
        # First, clear all existing organization owner flags for ALL users
        all_users = User.query.all()
        cleared_count = 0
        for user in all_users:
            if user.is_organization_owner:
                user.is_organization_owner = False
                cleared_count += 1
        
        print(f"✅ Cleared organization owner flags for {cleared_count} users")
        
        # Set flags for specified users
        updated_count = 0
        assigned_count = 0
        
        for username in owner_usernames:
            user = User.query.filter_by(username=username).first()
            
            if user:
                print(f"\n  Processing user: {username}")
                print(f"    User type: {user.user_type}")
                print(f"    Organization ID: {user.organization_id}")
                
                # Change user_type to customer if it's organization_owner
                if user.user_type == 'organization_owner':
                    user.user_type = 'customer'
                    print(f"    ✅ Changed user type from organization_owner to customer")
                
                # Set the organization owner flag (regardless of user type for now)
                user.is_organization_owner = True
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
        
        # Verify the results
        print("\n=== Verification ===")
        org_owners = User.query.filter_by(is_organization_owner=True).all()
        print(f"Found {len(org_owners)} users with organization owner flag:")
        
        for user in org_owners:
            has_role = any(
                assignment.is_active and assignment.role_id == org_owner_role.id
                for assignment in user.role_assignments
            )
            print(f"👤 {user.username}: Flag=True, Role={'✅ Yes' if has_role else '❌ No'}, Type={user.user_type}")
        
        print("=== Seeding Complete ===")
        return True

if __name__ == '__main__':
    seed_organization_owners()
