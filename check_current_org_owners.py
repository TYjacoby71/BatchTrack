
#!/usr/bin/env python3
"""Check current users with organization owner role"""

from app.models import User, Role, UserRoleAssignment
from app.extensions import db
from app import create_app

def check_current_org_owners():
    """Check which users currently have organization owner role"""
    
    app = create_app()
    with app.app_context():
        print("=== Current Organization Owner Role Assignments ===")
        
        # Get the organization owner system role
        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        
        if not org_owner_role:
            print("❌ Organization owner system role not found!")
            return False
        
        print(f"✅ Found organization owner role (ID: {org_owner_role.id}) with {len(org_owner_role.permissions)} permissions")
        print()
        
        # Find all active role assignments for organization owner role
        org_owner_assignments = UserRoleAssignment.query.filter_by(
            role_id=org_owner_role.id,
            is_active=True
        ).all()
        
        print(f"Found {len(org_owner_assignments)} active organization owner role assignments:")
        print()
        
        for assignment in org_owner_assignments:
            user = assignment.user
            print(f"👤 User: {user.username}")
            print(f"   Name: {user.first_name} {user.last_name}")
            print(f"   Email: {user.email}")
            print(f"   User Type: {user.user_type}")
            print(f"   Organization ID: {user.organization_id}")
            print(f"   is_organization_owner flag: {user.is_organization_owner}")
            print(f"   Is Active: {user.is_active}")
            print(f"   Role Assigned: {assignment.assigned_at}")
            if assignment.assigned_by:
                assigner = User.query.get(assignment.assigned_by)
                print(f"   Assigned By: {assigner.username if assigner else 'Unknown'}")
            print()
        
        # Also check users with is_organization_owner flag
        print("=== Users with is_organization_owner Flag ===")
        flagged_users = User.query.filter_by(is_organization_owner=True).all()
        
        print(f"Found {len(flagged_users)} users with is_organization_owner=True:")
        print()
        
        for user in flagged_users:
            # Check if they also have the role
            has_role = any(
                assignment.is_active and assignment.role_id == org_owner_role.id
                for assignment in user.role_assignments
            )
            
            print(f"👤 User: {user.username}")
            print(f"   Name: {user.first_name} {user.last_name}")
            print(f"   Has Organization Owner Role: {'✅ Yes' if has_role else '❌ No'}")
            print(f"   Organization ID: {user.organization_id}")
            print(f"   Is Active: {user.is_active}")
            print()
        
        # Summary
        role_count = len(org_owner_assignments)
        flag_count = len(flagged_users)
        
        print("=== Summary ===")
        print(f"Users with organization owner ROLE: {role_count}")
        print(f"Users with organization owner FLAG: {flag_count}")
        
        if role_count != flag_count:
            print("⚠️  Mismatch detected between role assignments and flags!")
        else:
            print("✅ Role assignments and flags are consistent")
        
        return True

if __name__ == '__main__':
    check_current_org_owners()
