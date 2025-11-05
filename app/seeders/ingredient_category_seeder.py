
import json
import os
from ..models import IngredientCategory, InventoryItem
from ..extensions import db

def seed_categories(organization_id=None):
    """Seed global ingredient categories from JSON files (shared across all organizations)"""

    print("🔧 Seeding global ingredient categories from JSON files...")

    # Read from the JSON files in global directory
    base_dir = os.path.join(os.path.dirname(__file__), 'globallist', 'ingredients', 'categories')

    if not os.path.exists(base_dir):
        print(f"⚠️  Ingredient categories directory not found: {base_dir}. Skipping.")
        return

    created_count = 0

    # Get all JSON files in the categories directory
    json_files = [f for f in os.listdir(base_dir) if f.endswith('.json') and not f.startswith('.')]

    if not json_files:
        print(f"⚠️  No JSON files found in {base_dir}. Skipping.")
        return

    for filename in json_files:
        filepath = os.path.join(base_dir, filename)

        try:
            with open(filepath, 'r') as f:
                category_data = json.load(f)
        except Exception as e:
            print(f"  ⚠️  Error loading {filename}: {e}")
            continue

        cat_name = category_data.get('category_name', '').strip()
        if not cat_name:
            print(f"  ⚠️  Skipping {filename} due to missing 'category_name'.")
            continue

        # Check if global category already exists (organization_id=None means global)
        existing = IngredientCategory.query.filter_by(
            name=cat_name,
            organization_id=None,
            is_global_category=True
        ).first()

        if not existing:
            # Create global category that all organizations can reference
            category = IngredientCategory(
                name=cat_name,
                description=category_data.get('description', ''),
                default_density=category_data.get('default_density'),
                organization_id=None,  # Global category - not owned by any organization
                is_active=True,
                is_global_category=True,  # This is a global reference category
                show_saponification_value=category_data.get('show_saponification_value', False),
                show_iodine_value=category_data.get('show_iodine_value', False),
                show_melting_point=category_data.get('show_melting_point', False),
                show_flash_point=category_data.get('show_flash_point', False),
                show_ph_value=category_data.get('show_ph_value', False),
                show_moisture_content=category_data.get('show_moisture_content', False),
                show_shelf_life_days=category_data.get('show_shelf_life_days', False),
                show_comedogenic_rating=category_data.get('show_comedogenic_rating', False)
            )
            db.session.add(category)
            created_count += 1
            print(f"      ✅ Created global category: {cat_name}")
        else:
            print(f"      ↻ Global category exists: {cat_name}")

    try:
        db.session.commit()
        print(f"✅ Seeded {created_count} new global ingredient categories")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error committing global ingredient categories: {e}")

    # Update all items in global Container category to have type='container'
    container_cat = IngredientCategory.query.filter_by(
        name='Container',
        organization_id=None,
        is_global_category=True
    ).first()
    if container_cat:
        from ..models import GlobalItem
        items = GlobalItem.query.filter_by(
            ingredient_category_id=container_cat.id,
            item_type='ingredient'
        ).all()
        updated_items_count = 0
        for item in items:
            if item.item_type != 'container':
                item.item_type = 'container'
                updated_items_count += 1
        if updated_items_count > 0:
            db.session.commit()
            print(f"      Updated {updated_items_count} global items to type 'container'")
        else:
            print(f"      No global items needed update to type 'container'")
