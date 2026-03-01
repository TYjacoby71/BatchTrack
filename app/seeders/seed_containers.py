import logging
import json
import os
import sys

logger = logging.getLogger(__name__)


# Add the parent directory to the Python path so we can import app
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app import create_app
from app.models import GlobalItem, db


def generate_container_attributes():
    """Generate JSON files for container attributes based on existing database data"""
    print("=== Generating Container Attributes ===")

    # Query distinct values from existing containers
    materials_query = (
        db.session.query(GlobalItem.container_material)
        .filter(
            GlobalItem.container_material.isnot(None),
            GlobalItem.item_type == "container",
        )
        .distinct()
        .all()
    )
    materials = sorted([m[0] for m in materials_query if m[0]])

    types_query = (
        db.session.query(GlobalItem.container_type)
        .filter(
            GlobalItem.container_type.isnot(None), GlobalItem.item_type == "container"
        )
        .distinct()
        .all()
    )
    types = sorted([t[0] for t in types_query if t[0]])

    styles_query = (
        db.session.query(GlobalItem.container_style)
        .filter(
            GlobalItem.container_style.isnot(None), GlobalItem.item_type == "container"
        )
        .distinct()
        .all()
    )
    styles = sorted([s[0] for s in styles_query if s[0]])

    colors_query = (
        db.session.query(GlobalItem.container_color)
        .filter(
            GlobalItem.container_color.isnot(None), GlobalItem.item_type == "container"
        )
        .distinct()
        .all()
    )
    colors = sorted([c[0] for c in colors_query if c[0]])

    # Create attributes directory
    attributes_dir = os.path.join(
        os.path.dirname(__file__), "globallist", "containers", "attributes"
    )
    os.makedirs(attributes_dir, exist_ok=True)

    # Create JSON files
    files_created = []

    if materials:
        materials_file = os.path.join(attributes_dir, "materials.json")
        with open(materials_file, "w") as f:
            json.dump({"materials": materials}, f, indent=2)
        files_created.append("materials.json")
        print(f"  ✅ Created materials.json with {len(materials)} materials")

    if types:
        types_file = os.path.join(attributes_dir, "types.json")
        with open(types_file, "w") as f:
            json.dump({"types": types}, f, indent=2)
        files_created.append("types.json")
        print(f"  ✅ Created types.json with {len(types)} types")

    if styles:
        styles_file = os.path.join(attributes_dir, "styles.json")
        with open(styles_file, "w") as f:
            json.dump({"styles": styles}, f, indent=2)
        files_created.append("styles.json")
        print(f"  ✅ Created styles.json with {len(styles)} styles")

    if colors:
        colors_file = os.path.join(attributes_dir, "colors.json")
        with open(colors_file, "w") as f:
            json.dump({"colors": colors}, f, indent=2)
        files_created.append("colors.json")
        print(f"  ✅ Created colors.json with {len(colors)} colors")

    return files_created


def seed_containers_from_files(selected_files):
    """Seed container items from JSON files"""
    if not selected_files:
        return 0

    print("\n=== Seeding Containers ===")
    created_items = 0

    base_dir = os.path.join(
        os.path.dirname(__file__), "globallist", "containers", "categories"
    )

    for filename in selected_files:
        filepath = os.path.join(base_dir, filename)

        try:
            with open(filepath, "r") as f:
                category_data = json.load(f)
        except Exception as e:
            logger.warning("Suppressed exception fallback at app/seeders/seed_containers.py:118", exc_info=True)
            print(f"  ⚠️  Error loading {filename}: {e}")
            continue

        cat_name = category_data.get("category_name", "").strip()
        print(f"\n📁 Processing container category: {cat_name}")

        items_in_category = 0
        for item_data in category_data.get("items", []):
            name = item_data.get("name", "").strip()
            if not name:
                continue

            # Check if item already exists
            existing_item = GlobalItem.query.filter_by(
                name=name, item_type="container"
            ).first()

            if existing_item:
                print(f"      ↻ Item exists: {name}")
                continue

            # Create new item
            new_item = GlobalItem(
                name=name,
                item_type="container",
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
        # First, generate attributes if database has existing containers
        existing_containers = GlobalItem.query.filter_by(item_type="container").count()
        if existing_containers > 0:
            print(
                f"Found {existing_containers} existing containers, generating attribute files..."
            )
            generate_container_attributes()

        # Get available container files
        base_dir = os.path.join(
            os.path.dirname(__file__), "globallist", "containers", "categories"
        )
        available_files = []
        if os.path.exists(base_dir):
            for filename in os.listdir(base_dir):
                if filename.endswith(".json") and not filename.startswith("."):
                    available_files.append(filename)

        if not available_files:
            print("No container JSON files found")
            sys.exit(1)

        print("\nAvailable container files:")
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

        items_created = seed_containers_from_files(selected_files)

        try:
            db.session.commit()
            print("\n🎉 Containers Seeding Complete!")
            print(f"📊 Items created: {items_created}")
        except Exception as e:
            logger.warning("Suppressed exception fallback at app/seeders/seed_containers.py:224", exc_info=True)
            db.session.rollback()
            print(f"\n❌ Seeding failed during commit: {e}")
