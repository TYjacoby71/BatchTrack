
#!/usr/bin/env python3

from app import create_app
from app.models import User, Organization, Role, UserRoleAssignment, InventoryItem
from app.extensions import db

def debug_org8_issues():
    """Debug organization 8 issues with admin user and dev user assignment"""
    app = create_app()
    
    with app.app_context():
        print("=== DEBUGGING ORGANIZATION 8 ISSUES ===")
        
        # Check organization 8
        org8 = Organization.query.get(8)
        if org8:
            print(f"\n=== Organization 8: {org8.name} ===")
            print(f"Active: {org8.is_active}")
            print(f"Subscription tier: {org8.effective_subscription_tier}")
            print(f"Users count: {len(org8.users)}")
            print(f"Active users: {org8.active_users_count}")
            
            print(f"\n=== All Users in Organization 8 ===")
            for user in org8.users:
                print(f"ID {user.id}: {user.username}")
                print(f"  Email: {user.email}")
                print(f"  User Type: {user.user_type}")
                print(f"  Active: {user.is_active}")
                print(f"  Organization Owner: {user.is_organization_owner}")
                print(f"  Organization ID: {user.organization_id}")
                
                # Check role assignments
                assignments = UserRoleAssignment.query.filter_by(
                    user_id=user.id,
                    is_active=True
                ).all()
                print(f"  Active Role Assignments: {len(assignments)}")
                for assignment in assignments:
                    role = Role.query.get(assignment.role_id)
                    print(f"    - Role: {role.name if role else 'UNKNOWN'} (ID: {assignment.role_id})")
                
                # Check permissions
                print(f"  Key Permissions:")
                for perm in ['recipes.edit', 'recipes.view', 'inventory.view', 'inventory.edit']:
                    has_perm = user.has_permission(perm)
                    status = "✅" if has_perm else "❌"
                    print(f"    {status} {perm}")
                print()
        else:
            print("❌ Organization 8 not found!")
            return
        
        # Check if dev user is wrongly assigned to org 8
        dev_user = User.query.filter_by(username='dev').first()
        if dev_user:
            print(f"=== DEV USER ISSUE ===")
            print(f"Dev user ID: {dev_user.id}")
            print(f"Dev user organization_id: {dev_user.organization_id}")
            print(f"Dev user type: {dev_user.user_type}")
            
            if dev_user.organization_id == 8:
                print("❌ PROBLEM: Dev user is assigned to organization 8!")
                print("Dev users should have organization_id = None")
                
                # Fix it
                dev_user.organization_id = None
                db.session.commit()
                print("✅ Fixed: Removed dev user from organization 8")
            else:
                print("✅ Dev user correctly has no organization assignment")
        
        # Check admin user specifically
        admin_user = User.query.filter_by(username='admin').first()
        if admin_user:
            print(f"\n=== ADMIN USER CHECK ===")
            print(f"Admin user ID: {admin_user.id}")
            print(f"Admin organization_id: {admin_user.organization_id}")
            print(f"Admin is_organization_owner: {admin_user.is_organization_owner}")
            
            if admin_user.organization_id == 8:
                print("Admin user is in organization 8")
                
                # Check organization owner role
                org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
                if org_owner_role:
                    existing_assignment = UserRoleAssignment.query.filter_by(
                        user_id=admin_user.id,
                        role_id=org_owner_role.id,
                        is_active=True
                    ).first()
                    
                    if not existing_assignment:
                        print("❌ Admin missing organization_owner role assignment")
                        assignment = UserRoleAssignment(
                            user_id=admin_user.id,
                            role_id=org_owner_role.id,
                            organization_id=admin_user.organization_id,
                            is_active=True
                        )
                        db.session.add(assignment)
                        
                        # Also ensure admin is marked as organization owner
                        admin_user.is_organization_owner = True
                        db.session.commit()
                        print("✅ Added organization_owner role to admin")
                    else:
                        print("✅ Admin has organization_owner role")
                else:
                    print("❌ organization_owner role not found!")
        
        # Check all organizations and their users
        print(f"\n=== ALL ORGANIZATIONS SUMMARY ===")
        all_orgs = Organization.query.all()
        for org in all_orgs:
            print(f"Org {org.id}: {org.name} - {len(org.users)} users")
            for user in org.users:
                print(f"  {user.username} (type: {user.user_type})")

if __name__ == '__main__':
    debug_org8_issues()
