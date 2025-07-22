
#!/usr/bin/env python3

from app import create_app
from app.models import User, Organization, Role, Permission, UserRoleAssignment
from app.utils.permissions import has_permission, get_user_permissions
from app.extensions import db

def debug_organization_permissions(org_name):
    """Debug permissions for a specific organization"""
    app = create_app()
    
    with app.app_context():
        # Find organization
        org = Organization.query.filter_by(name=org_name).first()
        if not org:
            print(f"❌ Organization '{org_name}' not found")
            return
        
        print(f"🏢 Organization: {org.name} (ID: {org.id})")
        print(f"📋 Subscription Tier: {org.subscription_tier}")
        print(f"👥 Users: {org.active_users_count}/{org.get_max_users()}")
        print()
        
        # Check users in organization
        users = User.query.filter_by(organization_id=org.id, is_active=True).all()
        
        for user in users:
            print(f"👤 User: {user.username} ({user.first_name} {user.last_name})")
            print(f"   User Type: {user.user_type}")
            
            # Check role assignments
            assignments = UserRoleAssignment.query.filter_by(
                user_id=user.id, 
                is_active=True
            ).all()
            
            if not assignments:
                print("   ❌ NO ROLE ASSIGNMENTS FOUND!")
            else:
                for assignment in assignments:
                    if assignment.role:
                        role = assignment.role
                        print(f"   🎭 Role: {role.name}")
                        print(f"      System Role: {role.is_system_role}")
                        print(f"      Permissions: {len(role.permissions)}")
                        
                        # List some key permissions
                        key_perms = ['dashboard.view', 'inventory.view', 'recipes.view', 'batches.view', 'organization.manage_users']
                        for perm in key_perms:
                            has_perm = has_permission(user, perm)
                            status = "✅" if has_perm else "❌"
                            print(f"      {status} {perm}")
            
            # Get all user permissions
            try:
                all_perms = []
                roles = user.get_active_roles()
                for role in roles:
                    all_perms.extend(role.get_permissions())
                print(f"   📝 Total Permissions: {len(all_perms)}")
            except Exception as e:
                print(f"   ❌ Error getting permissions: {e}")
            print()
        
        # Check organization owner role exists
        owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        if not owner_role:
            print("❌ CRITICAL: organization_owner system role does not exist!")
        else:
            print(f"✅ organization_owner role exists with {len(owner_role.permissions)} permissions")
            
            # Check if anyone has this role in this org
            owner_assignments = UserRoleAssignment.query.filter_by(
                role_id=owner_role.id,
                organization_id=org.id,
                is_active=True
            ).all()
            
            if not owner_assignments:
                print(f"❌ NO ONE has organization_owner role in {org.name}!")
            else:
                print(f"✅ {len(owner_assignments)} users have organization_owner role")

if __name__ == '__main__':
    debug_organization_permissions('test2 org')
