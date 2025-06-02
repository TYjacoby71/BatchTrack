
import json
import os
from datetime import datetime
from app import app, db
from models import InventoryItem, InventoryHistory, IngredientCategory
from utils.fifo_generator import generate_fifo_code

def load_inventory_from_json(json_file_path=None):
    """Load inventory items from JSON export file and create FIFO entries"""
    
    if json_file_path is None:
        json_file_path = "attached_assets/inventory_export_20250502_225444 (1).json"
    
    if not os.path.exists(json_file_path):
        print(f"❌ File not found: {json_file_path}")
        return False
    
    try:
        with open(json_file_path, 'r') as f:
            items_data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading JSON file: {e}")
        return False
    
    print(f"📦 Loading {len(items_data)} inventory items...")
    
    items_created = 0
    items_updated = 0
    fifo_entries_created = 0
    
    for item_data in items_data:
        try:
            # Check if item already exists
            existing_item = InventoryItem.query.filter_by(name=item_data['name']).first()
            
            if existing_item:
                print(f"⚠️  Item '{item_data['name']}' already exists, skipping...")
                items_updated += 1
                continue
            
            # Create new inventory item
            new_item = InventoryItem(
                name=item_data['name'],
                quantity=item_data['quantity'],
                unit=item_data.get('unit', ''),
                type=item_data.get('type', 'ingredient'),
                cost_per_unit=item_data.get('cost_per_unit', 0.0),
                low_stock_threshold=item_data.get('low_stock_threshold', 0.0),
                is_perishable=item_data.get('is_perishable', False),
                category_id=item_data.get('category_id'),
                density=item_data.get('density'),
                storage_amount=item_data.get('storage_amount', 0.0),
                storage_unit=item_data.get('storage_unit', '')
            )
            
            db.session.add(new_item)
            db.session.flush()  # Get the ID for FIFO entry
            
            # Create FIFO entry for items with quantity > 0
            if new_item.quantity > 0:
                fifo_code = generate_fifo_code("STARTUP")
                
                fifo_entry = InventoryHistory(
                    inventory_item_id=new_item.id,
                    change_type='restock',
                    quantity_change=new_item.quantity,
                    unit=new_item.unit,
                    remaining_quantity=new_item.quantity,
                    unit_cost=new_item.cost_per_unit,
                    note=f"Startup inventory load - {fifo_code}",
                    quantity_used=0,
                    created_by=None  # System load
                )
                
                db.session.add(fifo_entry)
                fifo_entries_created += 1
                
                print(f"✅ Created '{new_item.name}' with {new_item.quantity} {new_item.unit} (FIFO: {fifo_code})")
            else:
                print(f"✅ Created '{new_item.name}' with 0 quantity (no FIFO entry)")
            
            items_created += 1
            
        except Exception as e:
            print(f"❌ Error processing item '{item_data.get('name', 'Unknown')}': {e}")
            continue
    
    try:
        db.session.commit()
        print(f"\n🎉 Startup inventory load complete!")
        print(f"   Items created: {items_created}")
        print(f"   Items skipped: {items_updated}")
        print(f"   FIFO entries: {fifo_entries_created}")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error committing to database: {e}")
        return False

def categorize_startup_items():
    """Auto-categorize loaded items based on type and keywords"""
    
    # Get categories
    oil_cat = IngredientCategory.query.filter_by(name='Oil').first()
    wax_cat = IngredientCategory.query.filter_by(name='Wax').first()
    container_cat = IngredientCategory.query.filter_by(name='Container').first()
    fragrance_cat = IngredientCategory.query.filter_by(name='Fragrance').first()
    liquid_cat = IngredientCategory.query.filter_by(name='Liquid').first()
    
    # Keywords for auto-categorization
    categorization_rules = {
        'oil': oil_cat,
        'tallow': oil_cat,
        'castor': oil_cat,
        'wax': wax_cat,
        'beeswax': wax_cat,
        'essential oil': fragrance_cat,
        'lavender': fragrance_cat,
        'plate': container_cat,
        'tin': container_cat,
        'lemon': liquid_cat
    }
    
    items_categorized = 0
    
    # Get all uncategorized items
    uncategorized_items = InventoryItem.query.filter_by(category_id=None).all()
    
    for item in uncategorized_items:
        item_name_lower = item.name.lower()
        
        # Auto-categorize containers by type
        if item.type == 'container' and container_cat:
            item.category_id = container_cat.id
            items_categorized += 1
            print(f"📂 Categorized '{item.name}' as Container")
            continue
        
        # Check keywords
        for keyword, category in categorization_rules.items():
            if keyword in item_name_lower and category:
                item.category_id = category.id
                items_categorized += 1
                print(f"📂 Categorized '{item.name}' as {category.name}")
                break
    
    if items_categorized > 0:
        db.session.commit()
        print(f"✅ Auto-categorized {items_categorized} items")
    else:
        print("ℹ️  No items needed categorization")

def run_startup_inventory_loader():
    """Main function to run the complete startup inventory load process"""
    print("🚀 Starting inventory loader...")
    
    success = load_inventory_from_json()
    
    if success:
        print("\n📂 Auto-categorizing items...")
        categorize_startup_items()
        print("\n✅ Startup inventory loader completed successfully!")
    else:
        print("\n❌ Startup inventory loader failed!")
    
    return success

if __name__ == '__main__':
    with app.app_context():
        run_startup_inventory_loader()
