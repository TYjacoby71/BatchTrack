import logging
import os
import sys

logger = logging.getLogger(__name__)


# Add the parent directory to the Python path so we can import app
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app import create_app

from .seed_consumables import seed_consumables_from_files
from .seed_containers import generate_container_attributes, seed_containers_from_files

# Import the individual seeders
from .seed_ingredients import seed_ingredients_from_files
from .seed_packaging import seed_packaging_from_files


def get_available_json_files():
    """Get all available JSON files organized by type"""
    base_dir = os.path.join(os.path.dirname(__file__), "globallist")
    available_files = {
        "ingredients": [],
        "containers": [],
        "packaging": [],
        "consumables": [],
    }

    for item_type in available_files.keys():
        category_path = os.path.join(base_dir, item_type, "categories")
        if os.path.exists(category_path):
            for filename in os.listdir(category_path):
                if filename.endswith(".json") and not filename.startswith("."):
                    available_files[item_type].append(filename)

    return available_files


def seed_global_inventory_library():
    """Main seeder function that automatically seeds all available files"""
    app = create_app()
    with app.app_context():
        available_files = get_available_json_files()

        print("🔧 Seeding global inventory library...")

        total_categories = 0
        total_items = 0

        # 1. Ingredients
        try:
            categories_created, items_created = seed_ingredients_from_files(
                available_files.get("ingredients", [])
            )
            total_categories += categories_created
            total_items += items_created
        except Exception as e:
            logger.warning("Suppressed exception fallback at app/seeders/seed_global_inventory_library.py:57", exc_info=True)
            print(f"   ❌ Ingredients failed: {e}")

        # 2. Containers
        try:
            from app.models import GlobalItem, db

            existing_containers = GlobalItem.query.filter_by(
                item_type="container"
            ).count()
            if existing_containers > 0 and available_files.get("containers"):
                generate_container_attributes()

            items_created = seed_containers_from_files(
                available_files.get("containers", [])
            )
            total_items += items_created
        except Exception as e:
            logger.warning("Suppressed exception fallback at app/seeders/seed_global_inventory_library.py:74", exc_info=True)
            print(f"   ❌ Containers failed: {e}")

        # 3. Packaging
        try:
            items_created = seed_packaging_from_files(
                available_files.get("packaging", [])
            )
            total_items += items_created
        except Exception as e:
            logger.warning("Suppressed exception fallback at app/seeders/seed_global_inventory_library.py:83", exc_info=True)
            print(f"   ❌ Packaging failed: {e}")

        # 4. Consumables
        try:
            items_created = seed_consumables_from_files(
                available_files.get("consumables", [])
            )
            total_items += items_created
        except Exception as e:
            logger.warning("Suppressed exception fallback at app/seeders/seed_global_inventory_library.py:92", exc_info=True)
            print(f"   ❌ Consumables failed: {e}")

        try:
            db.session.commit()
            print(
                f"   ✅ Global inventory library: {total_categories} categories, {total_items} items"
            )
        except Exception as e:
            logger.warning("Suppressed exception fallback at app/seeders/seed_global_inventory_library.py:100", exc_info=True)
            db.session.rollback()
            print(f"   ❌ Global inventory library failed: {e}")


if __name__ == "__main__":
    seed_global_inventory_library()
