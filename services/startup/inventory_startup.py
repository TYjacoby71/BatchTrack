
import json
from app import app, db
from models import InventoryItem, IngredientCategory
from services.inventory_adjustment import process_inventory_adjustment
from datetime import datetime

JSON_PATH = 'inventory_export_20250502_225444.json'

def get_density_reference():
    """Load density reference data for ingredient categorization"""
    try:
        with open('data/density_reference.json', 'r') as f:
            data = json.load(f)
            return {item['name'].lower(): item for item in data['common_densities']}
    except FileNotFoundError:
        print("⚠️  Density reference file not found, continuing without density assignment")
        return {}

def startup_inventory_service():
    """Import legacy inventory using proper adjustment workflows"""
    with app.app_context():
        try:
            with open(JSON_PATH, 'r') as f:
                inventory_data = json.load(f)
        except FileNotFoundError:
            print(f"❌ Inventory file {JSON_PATH} not found")
            return False

        densities = get_density_reference()
        created_count = 0
        skipped_count = 0
        
        print("🚀 Starting inventory import service...")

        for item_data in inventory_data:
            # Check if item already exists
            existing = InventoryItem.query.filter_by(name=item_data['name']).first()
            if existing:
                print(f"[SKIPPED] {item_data['name']} already exists")
                skipped_count += 1
                continue

            # Create new inventory item with base properties
            new_item = InventoryItem(
                name=item_data['name'],
                quantity=0.0,  # Start with 0, will add via adjustment
                unit=item_data['unit'] or '',
                type=item_data['type'] or 'ingredient',
                cost_per_unit=item_data['cost_per_unit'] or 0.0,
                intermediate=item_data.get('intermediate', False),
                low_stock_threshold=item_data.get('low_stock_threshold', 0.0),
                storage_amount=item_data.get('storage_amount', 0.0),
                storage_unit=item_data.get('storage_unit', ''),
                is_perishable=item_data.get('is_perishable', False)
            )

            # Assign density and category from reference data
            name_lower = new_item.name.lower()
            if name_lower in densities:
                new_item.density = densities[name_lower]["density_g_per_ml"]
                cat_name = densities[name_lower]["category"]
                category = IngredientCategory.query.filter_by(name=cat_name).first()
                if category:
                    new_item.category_id = category.id

            # Save the item first to get an ID
            db.session.add(new_item)
            db.session.flush()
            
            # If there's initial quantity, add it via proper adjustment
            initial_quantity = item_data.get('quantity', 0.0)
            if initial_quantity > 0:
                try:
                    process_inventory_adjustment(
                        item_id=new_item.id,
                        quantity=initial_quantity,
                        change_type='restock',
                        unit=new_item.unit,
                        notes='Startup Service - Legacy Import',
                        created_by=1,  # System user
                        cost_override=new_item.cost_per_unit
                    )
                    print(f"[ADDED] {new_item.name} → {initial_quantity} {new_item.unit} (with FIFO entry)")
                except Exception as e:
                    print(f"[ERROR] Failed to add quantity for {new_item.name}: {str(e)}")
                    db.session.rollback()
                    continue
            else:
                print(f"[ADDED] {new_item.name} → 0 {new_item.unit} (no initial stock)")
            
            created_count += 1

        db.session.commit()
        print(f"✅ Inventory startup complete: {created_count} items created, {skipped_count} skipped")
        return True

if __name__ == '__main__':
    startup_inventory_service()
