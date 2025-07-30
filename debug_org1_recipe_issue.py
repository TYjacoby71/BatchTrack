
from app import create_app
from app.models import Organization, User, Role, Permission, InventoryItem
from app.extensions import db
from app.blueprints.developer.subscription_tiers import load_tiers_config

def debug_org1_recipe_issue():
    """Debug why org 1 users can't add ingredients to recipes"""
    app = create_app()
    
    with app.app_context():
        print("=== DEBUGGING ORGANIZATION AND USER ISSUES ===")
        
        # Show ALL organizations
        all_orgs = Organization.query.all()
        print(f"\n=== ALL ORGANIZATIONS IN DATABASE ({len(all_orgs)}) ===")
        for org in all_orgs:
            print(f"ID {org.id}: {org.name}")
            print(f"   Active: {org.is_active}")
            print(f"   Subscription tier: {org.effective_subscription_tier}")
            print(f"   Users: {len(org.users)}")
            print(f"   Active users: {org.active_users_count}")
        
        if len(all_orgs) == 0:
            print("❌ NO ORGANIZATIONS FOUND IN DATABASE!")
            return
        
        # Show ALL users
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
        
        # Check if we have specific user accounts mentioned
        problem_users = ['admin', 'manager', 'operator']
        print(f"\n=== CHECKING FOR SPECIFIC PROBLEM USERS ===")
        for username in problem_users:
            user = User.query.filter_by(username=username).first()
            if user:
                print(f"✅ Found user '{username}' (ID: {user.id}, Org: {user.organization_id})")
                
                # Check this user's permissions
                required_perms = ['recipes.edit', 'recipes.view', 'inventory.view', 'inventory.edit']
                for perm_name in required_perms:
                    has_perm = user.has_permission(perm_name)
                    print(f"     {perm_name}: {'✅' if has_perm else '❌'}")
            else:
                print(f"❌ User '{username}' not found")
        
        # Check ingredients for each organization
        print(f"\n=== INGREDIENTS BY ORGANIZATION ===")
        for org in all_orgs:
            ingredients = InventoryItem.query.filter(
                ~InventoryItem.type.in_(['product', 'product-reserved']),
                InventoryItem.organization_id == org.id
            ).all()
            print(f"Organization {org.id} ({org.name}): {len(ingredients)} ingredients")
            if len(ingredients) > 0:
                for ing in ingredients[:3]:
                    print(f"   - {ing.name} (Type: {ing.type})")
        
        # Check if permissions exist in database
        print(f"\n=== PERMISSION EXISTENCE CHECK ===")
        required_perms = ['recipes.edit', 'recipes.view', 'inventory.view', 'inventory.edit']
        for perm_name in required_perms:
            perm = Permission.query.filter_by(name=perm_name).first()
            if perm:
                print(f"✅ {perm_name} exists and is {'active' if perm.is_active else 'inactive'}")
            else:
                print(f"❌ {perm_name} MISSING from database!")

if __name__ == "__main__":
    debug_org1_recipe_issue()
