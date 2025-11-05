import json
import os
from flask_login import current_user
from ..models import IngredientCategory, InventoryItem
from ..extensions import db

def seed_categories(organization_id=None):
    """Seed ingredient categories for an organization using global JSON files"""

    if organization_id is None and current_user and current_user.is_authenticated:
        organization_id = current_user.organization_id

    if not organization_id:
        print("⚠️ Organization ID required for seeding categories. Skipping.")
        return

    # Read from the same JSON files used by global ingredient seeder
    base_dir = os.path.join(os.path.dirname(__file__), 'globallist', 'ingredients', 'categories')

    if not os.path.exists(base_dir):
        print(f"⚠️  Ingredient categories directory not found: {base_dir}. Skipping.")
        return

    print(f"🔧 Seeding organization-specific ingredient categories from JSON files for org ID: {organization_id}...")
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

        # Check if category already exists for this organization
        existing = IngredientCategory.query.filter_by(
            name=cat_name,
            organization_id=organization_id
        ).first()

        if not existing:
            # Create organization-specific category based on global category data
            category = IngredientCategory(
                name=cat_name,
                description=category_data.get('description', ''),
                default_density=category_data.get('default_density'),
                organization_id=organization_id,
                is_active=True,
                is_global_category=False,  # This is organization-specific
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
            print(f"      ✅ Created org category: {cat_name}")
        else:
            print(f"      ↻ Category exists: {cat_name}")

    try:
        db.session.commit()
        print(f"✅ Seeded {created_count} new ingredient categories for organization {organization_id}")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error committing ingredient categories for organization {organization_id}: {e}")

    # Update all items in Container category to have type='container'
    # This part remains the same as it correctly identifies and updates items.
    container_cat = IngredientCategory.query.filter_by(
        name='Container',
        organization_id=organization_id
    ).first()
    if container_cat:
        items = InventoryItem.query.filter_by(
            category_id=container_cat.id,
            organization_id=organization_id
        ).all()
        updated_items_count = 0
        for item in items:
            if item.type != 'container':
                item.type = 'container'
                updated_items_count += 1
        if updated_items_count > 0:
            db.session.commit()
            print(f"      Updated {updated_items_count} items to type 'container' for organization {organization_id}")
        else:
            print(f"      No items needed update to type 'container' for organization {organization_id}")