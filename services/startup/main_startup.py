
from app import app
from .unit_startup import startup_unit_service
from .inventory_startup import startup_inventory_service
from .recipe_startup import startup_recipe_service
from seeders.ingredient_category_seeder import seed_categories

def run_full_startup():
    """Run complete startup sequence for legacy data import"""
    print("🎯 BatchTrack Startup Service - Legacy Import")
    print("=" * 50)
    
    with app.app_context():
        # Step 1: Seed ingredient categories (required for inventory)
        print("\n📁 Step 1: Seeding ingredient categories...")
        try:
            seed_categories()
            print("✅ Ingredient categories seeded")
        except Exception as e:
            print(f"❌ Category seeding failed: {str(e)}")
            return False

        # Step 2: Import units
        print("\n📏 Step 2: Importing units...")
        try:
            if not startup_unit_service():
                print("❌ Unit import failed")
                return False
        except Exception as e:
            print(f"❌ Unit import error: {str(e)}")
            return False

        # Step 3: Import inventory items
        print("\n📦 Step 3: Importing inventory...")
        try:
            if not startup_inventory_service():
                print("❌ Inventory import failed")
                return False
        except Exception as e:
            print(f"❌ Inventory import error: {str(e)}")
            return False

        # Step 4: Import recipes
        print("\n🍳 Step 4: Importing recipes...")
        try:
            if not startup_recipe_service():
                print("❌ Recipe import failed")
                return False
        except Exception as e:
            print(f"❌ Recipe import error: {str(e)}")
            return False

    print("\n" + "=" * 50)
    print("🎉 BatchTrack startup complete! All legacy data imported successfully.")
    return True

if __name__ == '__main__':
    run_full_startup()
