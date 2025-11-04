
import json
import os
import sys
import glob

# Add the parent directory to the Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app
from app.models import db, GlobalItem, IngredientCategory


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


def load_category_file(item_type, filename):
    """Load a single category JSON file"""
    base_dir = os.path.join(os.path.dirname(__file__), 'globallist')
    filepath = os.path.join(base_dir, item_type, 'categories', filename)
    
    try:
        with open(filepath, 'r') as f:
            category_data = json.load(f)
            category_data['item_type'] = item_type.rstrip('s')  # Remove plural 's'
            return category_data
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return None


def seed_ingredient_categories_and_items(selected_files):
    """Seed ingredient categories first, then items"""
    if not selected_files.get('ingredients'):
        return 0, 0
    
    print("\n=== Seeding Ingredients ===")
    created_categories = 0
    created_items = 0
    
    for filename in selected_files['ingredients']:
        category_data = load_category_file('ingredients', filename)
        if not category_data:
            continue
            
        cat_name = category_data.get('category_name', '').strip()
        if not cat_name:
            print(f"  ⚠️  Skipping {filename} - no category name")
            continue
            
        print(f"\n📁 Processing ingredient category: {cat_name}")
        
        # Create or update ingredient category
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
            print(f"    ✅ Created category: {cat_name}")
        else:
            print(f"    ↻ Category exists: {cat_name}")
        
        category = existing_cat or new_cat
        
        # Seed items in this category
        items_in_category = 0
        for item_data in category_data.get('items', []):
            name = item_data.get('name', '').strip()
            if not name:
                continue
                
            # Check if item already exists
            existing_item = GlobalItem.query.filter_by(
                name=name,
                item_type='ingredient'
            ).first()
            
            if existing_item:
                print(f"      ↻ Item exists: {name}")
                continue
                
            # Create new item
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
            items_in_category += 1
            print(f"      ✅ Created item: {name}")
        
        print(f"    📦 Processed {items_in_category} items in {cat_name}")
    
    return created_categories, created_items


def seed_non_ingredient_items(item_type, selected_files):
    """Seed containers, packaging, or consumables"""
    if not selected_files.get(item_type):
        return 0
    
    print(f"\n=== Seeding {item_type.upper()} ===")
    created_items = 0
    
    for filename in selected_files[item_type]:
        category_data = load_category_file(item_type, filename)
        if not category_data:
            continue
            
        cat_name = category_data.get('category_name', '').strip()
        print(f"\n📁 Processing {item_type} category: {cat_name}")
        
        items_in_category = 0
        for item_data in category_data.get('items', []):
            name = item_data.get('name', '').strip()
            if not name:
                continue
                
            # Check if item already exists
            existing_item = GlobalItem.query.filter_by(
                name=name,
                item_type=item_type.rstrip('s')
            ).first()
            
            if existing_item:
                print(f"      ↻ Item exists: {name}")
                continue
                
            # Create new item
            new_item = GlobalItem(
                name=name,
                item_type=item_type.rstrip('s'),
                capacity=item_data.get('capacity'),
                capacity_unit=item_data.get('capacity_unit'),
                container_material=item_data.get('container_material'),
                container_type=item_data.get('container_type'),
                container_style=item_data.get('container_style'),
                container_color=item_data.get('container_color'),
                aka_names=item_data.get('aka_names', []),
                density=item_data.get('density_g_per_ml'),
                default_unit=item_data.get('default_unit'),
                default_is_perishable=item_data.get('perishable', False),
                recommended_shelf_life_days=item_data.get('shelf_life_days')
            )
            
            db.session.add(new_item)
            created_items += 1
            items_in_category += 1
            print(f"      ✅ Created item: {name}")
        
        print(f"    📦 Processed {items_in_category} items in {cat_name}")
    
    return created_items


def seed_global_inventory_library():
    """Main seeder function with interactive selection"""
    app = create_app()
    with app.app_context():
        selected_files = select_files_to_seed()
        if not selected_files:
            return
        
        print("\n=== Starting Global Inventory Library Seeding ===")
        
        # Seed in proper order
        total_categories = 0
        total_items = 0
        
        # 1. Ingredients (categories first, then items)
        categories_created, items_created = seed_ingredient_categories_and_items(selected_files)
        total_categories += categories_created
        total_items += items_created
        
        # 2. Containers
        items_created = seed_non_ingredient_items('containers', selected_files)
        total_items += items_created
        
        # 3. Packaging
        items_created = seed_non_ingredient_items('packaging', selected_files)
        total_items += items_created
        
        # 4. Consumables
        items_created = seed_non_ingredient_items('consumables', selected_files)
        total_items += items_created
        
        # Commit all changes
        try:
            db.session.commit()
            print(f"\n🎉 Global Inventory Library Seeding Complete!")
            print(f"📊 Summary:")
            print(f"   Categories created: {total_categories}")
            print(f"   Items created: {total_items}")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Seeding failed during commit: {e}")


if __name__ == '__main__':
    seed_global_inventory_library()
