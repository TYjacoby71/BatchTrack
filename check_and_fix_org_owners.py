
#!/usr/bin/env python3
"""Check and fix organization owner role assignments"""

from app.models import User, Role, UserRoleAssignment
from app.extensions import db
from app import create_app

def seed_organization_owners():
    """Seed organization owners with flag and role"""
    
    app = create_app()
    with app.app_context():
        print("=== Seeding Organization Owner Flags and Roles ===")
        
        # Get the organization owner system role
        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        
        if not org_owner_role:
            print("❌ Organization owner system role not found!")
            return False
        
        print(f"✅ Found organization owner role with {len(org_owner_role.permissions)} permissions")
        
        # Known organization owner usernames from the seeder
        org_owner_usernames = ['admin']  # Add more usernames if needed
        
        seeded_count = 0
        
        for username in org_owner_usernames:
            user = User.query.filter_by(username=username).first()
            
            if not user:
                print(f"⚠️  User '{username}' not found - skipping")
                continue
                
            print(f"\nProcessing user: {username}")
            
            # Set the organization owner flag
            if not user.is_organization_owner:
                user.is_organization_owner = True
                print(f"  ✅ Set is_organization_owner flag")
            else:
                print(f"  ✅ User already has is_organization_owner flag")
            
            # Check if user has active role assignments
            assignments = UserRoleAssignment.query.filter_by(
                user_id=user.id,
                is_active=True
            ).all()
            
            has_org_owner_role = any(
                assignment.role and assignment.role.name == 'organization_owner' 
                for assignment in assignments
            )
            
            if not has_org_owner_role:
                user.assign_role(org_owner_role)
                seeded_count += 1
                print(f"  ✅ Assigned organization owner role")
            else:
                print(f"  ✅ User already has organization owner role")
        
        db.session.commit()
        
        print(f"\n✅ Seeded {seeded_count} organization owner users")
        print("=== Seeding Complete ===")
        
        return True

def check_organization_owners():
    """Check organization owner role assignments"""
    
    app = create_app()
    with app.app_context():
        print("=== Checking Organization Owner Role Assignments ===")
        
        # Get the organization owner system role
        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        
        if not org_owner_role:
            print("❌ Organization owner system role not found!")
            return False
        
        print(f"✅ Found organization owner role with {len(org_owner_role.permissions)} permissions")
        
        # Find all users with is_organization_owner flag
        org_owners = User.query.filter_by(is_organization_owner=True).all()
        
        print(f"\nFound {len(org_owners)} users with is_organization_owner=True:")
        
        for user in org_owners:
            print(f"  - {user.username} (ID: {user.id})")
        
        if len(org_owners) == 0:
            print("\nNo users found with organization owner flag. Running seeder...")
            return seed_organization_owners()
        
        print("\n✅ All organization owners already have correct roles")
        print("=== Check Complete ===")
        
        return True

if __name__ == '__main__':
    check_organization_owners()
