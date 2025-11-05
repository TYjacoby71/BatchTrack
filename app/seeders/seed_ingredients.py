
import json
import os
import sys

# Add the parent directory to the Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app
from app.models import db, GlobalItem, IngredientCategory


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
                is_active=True,
                show_saponification_value=category_data.get('show_saponification_value', False),
                show_iodine_value=category_data.get('show_iodine_value', False),
                show_melting_point=category_data.get('show_melting_point', False),
                show_flash_point=category_data.get('show_flash_point', False),
                show_ph_value=category_data.get('show_ph_value', False),
                show_moisture_content=category_data.get('show_moisture_content', False),
                show_shelf_life_days=category_data.get('show_shelf_life_days', False),
                show_comedogenic_rating=category_data.get('show_comedogenic_rating', False)
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
                
            new_item = GlobalItem(
                name=name,
                item_type='ingredient',
                density=item_data.get('density_g_per_ml'),
                aka_names=item_data.get('aka_names', item_data.get('aka', [])),
                default_unit=item_data.get('default_unit'),
                ingredient_category_id=category.id,
                default_is_perishable=item_data.get('perishable', False),
                recommended_shelf_life_days=item_data.get('shelf_life_days'),
                saponification_value=item_data.get('saponification_value'),
                iodine_value=item_data.get('iodine_value'),
                melting_point_c=item_data.get('melting_point_c'),
                flash_point_c=item_data.get('flash_point_c'),
                ph_value=item_data.get('ph_value'),
                moisture_content_percent=item_data.get('moisture_content_percent'),
                comedogenic_rating=item_data.get('comedogenic_rating')
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
