
#!/usr/bin/env python3
"""Check and fix organization owner role assignments"""

from app.models import User, Role, UserRoleAssignment
from app.extensions import db
from app import create_app

def check_and_fix_org_owners():
    """Check organization owners and assign missing roles"""
    
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
        
        fixed_count = 0
        
        for user in org_owners:
            print(f"\n👤 User: {user.username} (ID: {user.id})")
            print(f"   Organization: {user.organization.name if user.organization else 'None'}")
            print(f"   User Type: {user.user_type}")
            print(f"   Is Org Owner Flag: {user.is_organization_owner}")
            
            # Check current role assignments
            assignments = UserRoleAssignment.query.filter_by(
                user_id=user.id,
                is_active=True
            ).all()
            
            print(f"   Active role assignments: {len(assignments)}")
            
            has_org_owner_role = False
            for assignment in assignments:
                if assignment.role:
                    print(f"     - Role: {assignment.role.name}")
                    if assignment.role.name == 'organization_owner':
                        has_org_owner_role = True
                elif assignment.developer_role:
                    print(f"     - Developer Role: {assignment.developer_role.name}")
            
            if not has_org_owner_role:
                print(f"   ⚠️  Missing organization owner role - fixing...")
                try:
                    user.assign_role(org_owner_role)
                    fixed_count += 1
                    print(f"   ✅ Assigned organization owner role")
                except Exception as e:
                    print(f"   ❌ Error assigning role: {e}")
            else:
                print(f"   ✅ Already has organization owner role")
        
        if fixed_count > 0:
            db.session.commit()
            print(f"\n✅ Fixed {fixed_count} organization owner users")
        else:
            print(f"\n✅ All organization owners already have correct roles")
        
        print("=== Check Complete ===")
        
        return True

if __name__ == '__main__':
    check_and_fix_org_owners()
