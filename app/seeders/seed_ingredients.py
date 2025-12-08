import json
import os
import sys

# Add the parent directory to the Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app
from app.models import db, GlobalItem, IngredientCategory

def parse_ph_range(ph_input):
    """Parses a pH input which can be a single value, a range 'X-Y', or None."""
    if ph_input is None:
        return None, None, None

    ph_input = str(ph_input).strip()

    if '-' in ph_input:
        try:
            ph_min_str, ph_max_str = ph_input.split('-', 1)
            ph_min = float(ph_min_str.strip())
            ph_max = float(ph_max_str.strip())
            # For a range, the displayed ph_value could be the average or simply the min
            ph_value = (ph_min + ph_max) / 2
            return ph_value, ph_min, ph_max
        except ValueError:
            # If splitting or conversion fails, treat it as a single value or invalid
            pass

    try:
        ph_value = float(ph_input)
        return ph_value, None, None
    except ValueError:
        # If it's not a range and not a float, return None for all
        return None, None, None


def seed_ingredients_from_files(selected_files):
    """Seed ingredient categories first, then items"""
    if not selected_files:
        return 0, 0

    created_categories = 0
    created_items = 0

    base_dir = os.path.join(os.path.dirname(__file__), 'globallist', 'ingredients', 'categories')

    for filename in selected_files:
        filepath = os.path.join(base_dir, filename)

        try:
            with open(filepath, 'r') as f:
                category_data = json.load(f)
        except Exception:
            continue

        cat_name = category_data.get('category_name', '').strip()
        if not cat_name:
            continue

        existing_cat = IngredientCategory.query.filter_by(name=cat_name, organization_id=None).first()
        if not existing_cat:
            new_cat = IngredientCategory(
                name=cat_name,
                description=category_data.get('description', ''),
                default_density=category_data.get('default_density'),
                is_global_category=True,
                organization_id=None,
                is_active=True
            )
            db.session.add(new_cat)
            db.session.flush()
            created_categories += 1

        category = existing_cat or new_cat

        for item_data in category_data.get('items', []):
            name = item_data.get('name', '').strip()
            if not name:
                continue

            existing_item = GlobalItem.query.filter_by(
                name=name,
                item_type='ingredient'
            ).first()

            if existing_item:
                continue

            # Parse pH range if present
            ph_value, ph_min, ph_max = parse_ph_range(item_data.get('ph_value'))

            new_item = GlobalItem(
                name=name,
                item_type='ingredient',
                ingredient_category_id=category.id,
                aliases=item_data.get('aliases', []),
                density=item_data.get('density', category_data.get('default_density')),
                default_unit=item_data.get('default_unit', 'gram'),
                
                recommended_fragrance_load_pct=item_data.get('recommended_fragrance_load_pct'),
                recommended_shelf_life_days=item_data.get('recommended_shelf_life_days'),
                inci_name=item_data.get('inci_name'),
                certifications=item_data.get('certifications', []),
                is_active_ingredient=item_data.get('is_active_ingredient', False),

                # Chemical/Physical properties
                saponification_value=item_data.get('saponification_value'),
                iodine_value=item_data.get('iodine_value'),
                melting_point_c=item_data.get('melting_point_c'),
                flash_point_c=item_data.get('flash_point_c'),
                ph_value=ph_value,
                ph_min=ph_min,
                ph_max=ph_max,
                moisture_content_percent=item_data.get('moisture_content_percent'),
                comedogenic_rating=item_data.get('comedogenic_rating'),
                fatty_acid_profile=item_data.get('fatty_acid_profile'),

                # Baking
                protein_content_pct=item_data.get('protein_content_pct'),

                # Brewing
                brewing_color_srm=item_data.get('brewing_color_srm'),
                brewing_potential_sg=item_data.get('brewing_potential_sg'),
                brewing_diastatic_power_lintner=item_data.get('brewing_diastatic_power_lintner'),

                metadata_json=item_data.get('metadata_json', {})
            )

            db.session.add(new_item)
            created_items += 1

    return created_categories, created_items


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        # Get available ingredient files
        base_dir = os.path.join(os.path.dirname(__file__), 'globallist', 'ingredients', 'categories')
        available_files = []
        if os.path.exists(base_dir):
            for filename in os.listdir(base_dir):
                if filename.endswith('.json') and not filename.startswith('.'):
                    available_files.append(filename)

        if not available_files:
            print("No ingredient JSON files found")
            sys.exit(1)

        print("Available ingredient files:")
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
                indices = [int(x.strip()) - 1 for x in selection.split(',')]
                selected_files = [available_files[i] for i in indices if 0 <= i < len(available_files)]
            except (ValueError, IndexError):
                print("Invalid selection")
                sys.exit(1)
        else:
            print("Invalid choice")
            sys.exit(1)

        categories_created, items_created = seed_ingredients_from_files(selected_files)

        try:
            db.session.commit()
            print(f"\n🎉 Ingredients Seeding Complete!")
            print(f"📊 Categories created: {categories_created}")
            print(f"📊 Items created: {items_created}")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Seeding failed during commit: {e}")