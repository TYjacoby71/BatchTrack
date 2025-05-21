
import json
from app import app, db
from models import InventoryItem, IngredientCategory, InventoryHistory
from datetime import datetime

# Path to your legacy inventory export
JSON_PATH = 'inventory_export_20250502_225444.json'

def get_density_reference():
    with open('data/density_reference.json', 'r') as f:
        data = json.load(f)
        return {item['name'].lower(): item for item in data['common_densities']}

def load_legacy_inventory():
    with app.app_context():
        with open(JSON_PATH, 'r') as f:
            inventory_data = json.load(f)

        for item in inventory_data:
            existing = InventoryItem.query.filter_by(name=item['name']).first()
            if existing:
                print(f"[SKIPPED] {item['name']} already exists.")
                continue

            new_item = InventoryItem(
                name=item['name'],
                quantity=item['quantity'] or 0.0,
                unit=item['unit'] or '',
                type=item['type'] or 'ingredient',
                cost_per_unit=item['cost_per_unit'] or 0.0,
                intermediate=item.get('intermediate', False),
                low_stock_threshold=item.get('low_stock_threshold', 0.0),
                storage_amount=item.get('storage_amount', 0.0),
                storage_unit=item.get('storage_unit', ''),
                shelf_life_days=item.get('shelf_life_days'),
                is_perishable=item.get('is_perishable', False)
            )

            # Look up density from reference data
            densities = get_density_reference()
            name_lower = new_item.name.lower()

            if name_lower in densities:
                new_item.density = densities[name_lower]["density_g_per_ml"]
                cat_name = densities[name_lower]["category"]
                category = IngredientCategory.query.filter_by(name=cat_name).first()
                if category:
                    new_item.category_id = category.id

            db.session.add(new_item)
            db.session.flush()  # Get the ID

            # Create initial FIFO history entry if quantity exists
            if new_item.quantity > 0:
                history = InventoryHistory(
                    inventory_item_id=new_item.id,
                    change_type='restock',
                    quantity_change=new_item.quantity,
                    remaining_quantity=new_item.quantity,
                    unit_cost=new_item.cost_per_unit,
                    quantity_used=0,
                    note='Initial import',
                    is_perishable=new_item.is_perishable,
                    expiration_date=datetime.utcnow() if new_item.is_perishable else None,
                    shelf_life_days=new_item.shelf_life_days,
                    created_by=1  # System user
                )
                db.session.add(history)
                print(f'[HISTORY] Created initial FIFO entry for {new_item.quantity} {new_item.unit}')
            density_str = f' (density: {new_item.density} g/ml)' if new_item.density else ''
            print(f'[ADDED] {new_item.name} → {new_item.quantity} {new_item.unit}{density_str}')

        db.session.commit()
        print("✅ Legacy inventory import complete.")

if __name__ == '__main__':
    load_legacy_inventory()
