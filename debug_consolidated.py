
#!/usr/bin/env python3

import sys
from app import create_app
from app.models import User, Organization, Role, Permission, UserRoleAssignment, InventoryItem
from app.utils.permissions import has_permission, get_user_permissions
from app.extensions import db

def debug_organization_permissions(org_id_or_name):
    """Debug permissions for a specific organization by ID or name"""
    app = create_app()
    
    with app.app_context():
        # Find organization by ID or name
        if org_id_or_name.isdigit():
            org = Organization.query.get(int(org_id_or_name))
        else:
            org = Organization.query.filter_by(name=org_id_or_name).first()
            
        if not org:
            print(f"❌ Organization '{org_id_or_name}' not found")
            return
        
        print(f"🏢 Organization: {org.name} (ID: {org.id})")
        subscription_tier = org.effective_subscription_tier if hasattr(org, 'effective_subscription_tier') else 'free'
        print(f"📋 Subscription Tier: {subscription_tier}")
        print(f"👥 Users: {org.active_users_count}/{org.get_max_users()}")
        print(f"🔹 Active: {org.is_active}")
        print()
        
        # Check users in organization
        users = User.query.filter_by(organization_id=org.id, is_active=True).all()
        
        for user in users:
            print(f"👤 User: {user.username} ({user.first_name} {user.last_name})")
            print(f"   User Type: {user.user_type}")
            print(f"   Email: {user.email}")
            print(f"   Is Organization Owner: {user.is_organization_owner}")
            
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
                        key_perms = ['dashboard.view', 'inventory.view', 'recipes.view', 'batches.view', 'organization.manage_users', 'recipes.edit', 'inventory.edit']
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
        
        # Check ingredients for this organization
        ingredients = InventoryItem.query.filter(
            ~InventoryItem.type.in_(['product', 'product-reserved']),
            InventoryItem.organization_id == org.id
        ).all()
        print(f"🧪 Ingredients: {len(ingredients)}")
        if len(ingredients) > 0:
            for ing in ingredients[:3]:
                print(f"   - {ing.name} (Type: {ing.type})")
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

def debug_all_organizations():
    """Debug all organizations in the system"""
    app = create_app()
    
    with app.app_context():
        print("=== DEBUGGING ALL ORGANIZATIONS ===")
        
        all_orgs = Organization.query.all()
        print(f"\n=== ALL ORGANIZATIONS IN DATABASE ({len(all_orgs)}) ===")
        
        if len(all_orgs) == 0:
            print("❌ NO ORGANIZATIONS FOUND IN DATABASE!")
            return
        
        for org in all_orgs:
            print(f"\nID {org.id}: {org.name}")
            print(f"   Active: {org.is_active}")
            print(f"   Subscription tier: {org.effective_subscription_tier}")
            print(f"   Users: {len(org.users)}")
            print(f"   Active users: {org.active_users_count}")
            
            # Show users in this org
            for user in org.users:
                print(f"     - {user.username} (type: {user.user_type}, active: {user.is_active})")
        
        # Show all users and their org assignments
        all_users = User.query.all()
        print(f"\n=== ALL USERS IN DATABASE ({len(all_users)}) ===")
        for user in all_users:
            print(f"ID {user.id}: {user.username}")
            print(f"   Email: {user.email}")
            print(f"   Organization ID: {user.organization_id}")
            print(f"   User Type: {user.user_type}")
            print(f"   Active: {user.is_active}")
            if user.organization_id:
                org = Organization.query.get(user.organization_id)
                print(f"   Organization Name: {org.name if org else 'NOT FOUND'}")
        
        # Check for dev users wrongly assigned to organizations
        print(f"\n=== DEV USER ISSUES CHECK ===")
        dev_users = User.query.filter_by(user_type='developer').all()
        for dev_user in dev_users:
            if dev_user.organization_id is not None:
                print(f"❌ PROBLEM: Dev user '{dev_user.username}' is assigned to organization {dev_user.organization_id}!")
                print("   Dev users should have organization_id = None")
            else:
                print(f"✅ Dev user '{dev_user.username}' correctly has no organization assignment")
        
        # Check permissions existence
        print(f"\n=== PERMISSION EXISTENCE CHECK ===")
        required_perms = ['recipes.edit', 'recipes.view', 'inventory.view', 'inventory.edit', 'dashboard.view', 'batches.view']
        for perm_name in required_perms:
            perm = Permission.query.filter_by(name=perm_name).first()
            if perm:
                print(f"✅ {perm_name} exists and is {'active' if perm.is_active else 'inactive'}")
            else:
                print(f"❌ {perm_name} MISSING from database!")

def fix_dev_user_assignments():
    """Fix dev users that are wrongly assigned to organizations"""
    app = create_app()
    
    with app.app_context():
        print("=== FIXING DEV USER ASSIGNMENTS ===")
        
        dev_users = User.query.filter_by(user_type='developer').all()
        fixed_count = 0
        
        for dev_user in dev_users:
            if dev_user.organization_id is not None:
                print(f"Fixing dev user '{dev_user.username}' - removing from organization {dev_user.organization_id}")
                dev_user.organization_id = None
                fixed_count += 1
        
        if fixed_count > 0:
            db.session.commit()
            print(f"✅ Fixed {fixed_count} dev user(s)")
        else:
            print("✅ No dev users needed fixing")

def check_specific_users(usernames):
    """Check specific users by username"""
    app = create_app()
    
    with app.app_context():
        print(f"=== CHECKING SPECIFIC USERS: {', '.join(usernames)} ===")
        
        for username in usernames:
            user = User.query.filter_by(username=username).first()
            if user:
                print(f"✅ Found user '{username}' (ID: {user.id}, Org: {user.organization_id})")
                
                # Check this user's permissions
                required_perms = ['recipes.edit', 'recipes.view', 'inventory.view', 'inventory.edit', 'dashboard.view']
                for perm_name in required_perms:
                    has_perm = user.has_permission(perm_name)
                    print(f"     {perm_name}: {'✅' if has_perm else '❌'}")
            else:
                print(f"❌ User '{username}' not found")

def show_usage():
    """Show usage information"""
    print("""
Usage: python debug_consolidated.py [command] [args]

Commands:
  org <id_or_name>     Debug specific organization by ID or name
  all                  Debug all organizations in the system
  fix-dev             Fix dev users wrongly assigned to organizations
  users <user1,user2>  Check specific users (comma-separated)
  
Examples:
  python debug_consolidated.py org 8
  python debug_consolidated.py org "test2 org"
  python debug_consolidated.py all
  python debug_consolidated.py fix-dev
  python debug_consolidated.py users admin,manager,operator
""")

def main():
    if len(sys.argv) < 2:
        show_usage()
        return
    
    command = sys.argv[1].lower()
    
    if command == 'org':
        if len(sys.argv) < 3:
            print("❌ Please specify organization ID or name")
            show_usage()
            return
        org_id_or_name = sys.argv[2]
        debug_organization_permissions(org_id_or_name)
        
    elif command == 'all':
        debug_all_organizations()
        
    elif command == 'fix-dev':
        fix_dev_user_assignments()
        
    elif command == 'users':
        if len(sys.argv) < 3:
            print("❌ Please specify usernames (comma-separated)")
            show_usage()
            return
        usernames = [u.strip() for u in sys.argv[2].split(',')]
        check_specific_users(usernames)
        
    else:
        print(f"❌ Unknown command: {command}")
        show_usage()

if __name__ == '__main__':
    main()
