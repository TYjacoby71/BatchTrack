import json
import os
import sys

# Add the parent directory to the Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app

# Import the individual seeders
from .seed_ingredients import seed_ingredients_from_files
from .seed_containers import seed_containers_from_files, generate_container_attributes
from .seed_packaging import seed_packaging_from_files
from .seed_consumables import seed_consumables_from_files


def get_available_json_files():
    """Get all available JSON files organized by type"""
    base_dir = os.path.join(os.path.dirname(__file__), 'globallist')
    available_files = {
        'ingredients': [],
        'containers': [],
        'packaging': [],
        'consumables': []
    }

    for item_type in available_files.keys():
        category_path = os.path.join(base_dir, item_type, 'categories')
        if os.path.exists(category_path):
            for filename in os.listdir(category_path):
                if filename.endswith('.json') and not filename.startswith('.'):
                    available_files[item_type].append(filename)

    return available_files


def select_files_to_seed():
    """Interactive file selection"""
    available_files = get_available_json_files()

    print("=== Global Item Library Seeder ===")
    print("Available JSON files to seed:")

    for item_type, files in available_files.items():
        if files:
            print(f"\n{item_type.upper()}:")
            for i, filename in enumerate(files, 1):
                print(f"  {i}. {filename}")

    print("\nOptions:")
    print("1. Seed all files")
    print("2. Select specific files")

    choice = input("\nEnter your choice (1 or 2): ").strip()

    if choice == "1":
        return available_files
    elif choice == "2":
        selected_files = {
            'ingredients': [],
            'containers': [],
            'packaging': [],
            'consumables': []
        }

        for item_type, files in available_files.items():
            if files:
                print(f"\nSelect {item_type} files to seed (comma-separated numbers, or 'all', or 'skip'):")
                for i, filename in enumerate(files, 1):
                    print(f"  {i}. {filename}")

                selection = input(f"{item_type} selection: ").strip().lower()

                if selection == 'all':
                    selected_files[item_type] = files
                elif selection == 'skip':
                    continue
                else:
                    try:
                        indices = [int(x.strip()) - 1 for x in selection.split(',')]
                        selected_files[item_type] = [files[i] for i in indices if 0 <= i < len(files)]
                    except (ValueError, IndexError):
                        print(f"Invalid selection for {item_type}, skipping...")

        return selected_files
    else:
        print("Invalid choice, exiting...")
        return None


def seed_global_inventory_library():
    """Main seeder function with interactive selection that calls individual seeders"""
    app = create_app()
    with app.app_context():
        selected_files = select_files_to_seed()
        if not selected_files:
            return

        print("\n=== Starting Global Inventory Library Seeding ===")
        print("📋 Seeding order: Ingredients → Containers → Packaging → Consumables")

        # Seed in proper dependency order
        total_categories = 0
        total_items = 0

        # 1. Ingredients (categories first, then items) - HAS DEPENDENCIES
        print("\n🔹 Step 1: Ingredients (with categories)")
        try:
            categories_created, items_created = seed_ingredients_from_files(selected_files.get('ingredients', []))
            total_categories += categories_created
            total_items += items_created
            print(f"   ✅ Ingredients: {categories_created} categories, {items_created} items")
        except Exception as e:
            print(f"   ❌ Ingredients failed: {e}")

        # 2. Containers (attributes first, then items) - HAS DEPENDENCIES
        print("\n🔹 Step 2: Containers (with attributes)")
        try:
            # Generate attributes if we have existing containers
            from app.models import db, GlobalItem
            existing_containers = GlobalItem.query.filter_by(item_type='container').count()
            if existing_containers > 0 and selected_files.get('containers'):
                print("   📋 Generating container attributes from existing data...")
                generate_container_attributes()

            items_created = seed_containers_from_files(selected_files.get('containers', []))
            total_items += items_created
            print(f"   ✅ Containers: {items_created} items")
        except Exception as e:
            print(f"   ❌ Containers failed: {e}")

        # 3. Packaging - NO DEPENDENCIES
        print("\n🔹 Step 3: Packaging")
        try:
            items_created = seed_packaging_from_files(selected_files.get('packaging', []))
            total_items += items_created
            print(f"   ✅ Packaging: {items_created} items")
        except Exception as e:
            print(f"   ❌ Packaging failed: {e}")

        # 4. Consumables - NO DEPENDENCIES
        print("\n🔹 Step 4: Consumables")
        try:
            items_created = seed_consumables_from_files(selected_files.get('consumables', []))
            total_items += items_created
            print(f"   ✅ Consumables: {items_created} items")
        except Exception as e:
            print(f"   ❌ Consumables failed: {e}")

        # Commit all changes
        try:
            db.session.commit()
            print(f"\n🎉 Global Inventory Library Seeding Complete!")
            print(f"📊 Summary:")
            print(f"   Categories created: {total_categories}")
            print(f"   Items created: {total_items}")
            print(f"📋 Seeding was additive - existing items were preserved")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Seeding failed during final commit: {e}")


if __name__ == '__main__':
    seed_global_inventory_library()