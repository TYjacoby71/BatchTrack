import json
import os
import sys

# Add the parent directory to the Python path so we can import app
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app import create_app
from app.models import GlobalItem, db


def seed_packaging_from_files(selected_files):
    """Seed packaging items from JSON files"""
    if not selected_files:
        return 0

    print("\n=== Seeding Packaging ===")
    created_items = 0

    base_dir = os.path.join(
        os.path.dirname(__file__), "globallist", "packaging", "categories"
    )

    for filename in selected_files:
        filepath = os.path.join(base_dir, filename)

        try:
            with open(filepath, "r") as f:
                category_data = json.load(f)
        except Exception as e:
            print(f"  ⚠️  Error loading {filename}: {e}")
            continue

        cat_name = category_data.get("category_name", "").strip()
        print(f"\n📁 Processing packaging category: {cat_name}")

        items_in_category = 0
        for item_data in category_data.get("items", []):
            name = item_data.get("name", "").strip()
            if not name:
                continue

            # Check if item already exists
            existing_item = GlobalItem.query.filter_by(
                name=name, item_type="packaging"
            ).first()

            if existing_item:
                print(f"      ↻ Item exists: {name}")
                continue

            # Create new item
            new_item = GlobalItem(
                name=name,
                item_type="packaging",
                capacity=item_data.get("capacity"),
                capacity_unit=item_data.get("capacity_unit"),
                container_material=item_data.get("container_material"),
                container_type=item_data.get("container_type"),
                container_style=item_data.get("container_style"),
                container_color=item_data.get("container_color"),
                aliases=item_data.get("aka_names", []),
                density=item_data.get("density_g_per_ml"),
                default_unit=item_data.get("default_unit"),
                default_is_perishable=item_data.get("perishable", False),
                recommended_shelf_life_days=item_data.get("shelf_life_days"),
            )

            db.session.add(new_item)
            created_items += 1
            items_in_category += 1
            print(f"      ✅ Created item: {name}")

        print(f"    📦 Processed {items_in_category} items in {cat_name}")

    return created_items


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        # Get available packaging files
        base_dir = os.path.join(
            os.path.dirname(__file__), "globallist", "packaging", "categories"
        )
        available_files = []
        if os.path.exists(base_dir):
            for filename in os.listdir(base_dir):
                if filename.endswith(".json") and not filename.startswith("."):
                    available_files.append(filename)

        if not available_files:
            print("No packaging JSON files found")
            sys.exit(1)

        print("Available packaging files:")
        for i, filename in enumerate(available_files, 1):
            print(f"  {i}. {filename}")

        print("\nOptions:")
        print("1. Seed all files")
        print("2. Select specific files")

        choice = input("\nEnter your choice (1 or 2): ").strip()

        if choice == "1":
            selected_files = available_files
        elif choice == "2":
            selection = input("Enter file numbers (comma-separated): ").strip()
            try:
                indices = [int(x.strip()) - 1 for x in selection.split(",")]
                selected_files = [
                    available_files[i] for i in indices if 0 <= i < len(available_files)
                ]
            except (ValueError, IndexError):
                print("Invalid selection")
                sys.exit(1)
        else:
            print("Invalid choice")
            sys.exit(1)

        items_created = seed_packaging_from_files(selected_files)

        try:
            db.session.commit()
            print("\n🎉 Packaging Seeding Complete!")
            print(f"📊 Items created: {items_created}")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Seeding failed during commit: {e}")
