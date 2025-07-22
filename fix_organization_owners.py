
#!/usr/bin/env python3
"""Fix organization owner role assignments"""

from app.models import User, Role, UserRoleAssignment
from app.extensions import db
from app import create_app

def fix_organization_owners():
    """Assign organization owner role to users who don't have proper role assignments"""
    
    app = create_app()
    with app.app_context():
        print("=== Fixing Organization Owner Role Assignments ===")
        
        # Get the organization owner system role
        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        
        if not org_owner_role:
            print("❌ Organization owner system role not found!")
            return False
        
        print(f"✅ Found organization owner role with {len(org_owner_role.permissions)} permissions")
        
        # Find all organization owner users
        org_owners = User.query.filter_by(user_type='organization_owner').all()
        
        print(f"Found {len(org_owners)} organization owner users")
        
        fixed_count = 0
        
        for user in org_owners:
            print(f"\nChecking user: {user.username}")
            
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
                print(f"  ⚠️  User missing organization owner role - fixing...")
                user.assign_role(org_owner_role)
                fixed_count += 1
                print(f"  ✅ Assigned organization owner role")
            else:
                print(f"  ✅ User already has organization owner role")
        
        db.session.commit()
        
        print(f"\n✅ Fixed {fixed_count} organization owner users")
        print("=== Fix Complete ===")
        
        return True

if __name__ == '__main__':
    fix_organization_owners()
