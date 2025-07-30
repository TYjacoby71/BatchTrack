
from app import create_app
from app.models import Organization, User, Role, Permission, InventoryItem
from app.extensions import db
from app.blueprints.developer.subscription_tiers import load_tiers_config

def debug_org1_recipe_issue():
    """Debug why org 1 users can't add ingredients to recipes"""
    app = create_app()
    
    with app.app_context():
        print("=== DEBUGGING ORG 1 RECIPE INGREDIENT ISSUE ===")
        
        # Check Organization 1
        org1 = Organization.query.get(1)
        if not org1:
            print("❌ Organization 1 not found!")
            return
            
        print(f"✅ Organization 1: {org1.name}")
        print(f"   Active: {org1.is_active}")
        print(f"   Subscription tier: {org1.effective_subscription_tier}")
        
        # Check subscription tier permissions
        tiers_config = load_tiers_config()
        tier_data = tiers_config.get(org1.effective_subscription_tier, {})
        tier_permissions = tier_data.get('permissions', [])
        
        print(f"\n=== TIER PERMISSIONS ({len(tier_permissions)} total) ===")
        required_perms = ['recipes.edit', 'recipes.view', 'inventory.view', 'inventory.edit']
        for perm_name in required_perms:
            if perm_name in tier_permissions:
                print(f"✅ {perm_name} - included in tier")
            else:
                print(f"❌ {perm_name} - MISSING from tier")
        
        # Check ingredients available to org 1
        ingredients = InventoryItem.query.filter(
            ~InventoryItem.type.in_(['product', 'product-reserved']),
            InventoryItem.organization_id == 1
        ).all()
        
        print(f"\n=== INGREDIENTS AVAILABLE TO ORG 1 ===")
        print(f"Total ingredients: {len(ingredients)}")
        if len(ingredients) == 0:
            print("❌ NO INGREDIENTS FOUND - this could be the issue!")
        else:
            print("✅ Ingredients exist")
            for ing in ingredients[:3]:
                print(f"   - {ing.name} (Type: {ing.type})")
        
        # Check users and their permissions
        print(f"\n=== ORG 1 USERS ===")
        for user in org1.users:
            if user.is_active:
                print(f"\nUser: {user.username}")
                print(f"  Type: {user.user_type}")
                print(f"  Active role assignments: {len([a for a in user.role_assignments if a.is_active])}")
                
                # Check specific permissions
                for perm_name in required_perms:
                    has_perm = user.has_permission(perm_name)
                    print(f"  {perm_name}: {'✅' if has_perm else '❌'}")
        
        # Check if permissions exist in database
        print(f"\n=== PERMISSION EXISTENCE CHECK ===")
        for perm_name in required_perms:
            perm = Permission.query.filter_by(name=perm_name).first()
            if perm:
                print(f"✅ {perm_name} exists and is {'active' if perm.is_active else 'inactive'}")
            else:
                print(f"❌ {perm_name} MISSING from database!")

if __name__ == "__main__":
    debug_org1_recipe_issue()
