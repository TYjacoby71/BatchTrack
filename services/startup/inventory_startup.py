
from app import app, db
from models import InventoryItem, IngredientCategory, InventoryHistory
import json

def get_density_reference():
    """Load density reference data for categorizing ingredients"""
    try:
        with open('data/density_reference.json', 'r') as f:
            data = json.load(f)
            return {item['name'].lower(): item for item in data['common_densities']}
    except FileNotFoundError:
        return {}

def load_startup_inventory():
    """Load startup inventory items with FIFO history tracking"""
    with app.app_context():
        # Check if we have the legacy export file
        try:
            with open('inventory_export_20250502_225444.json', 'r') as f:
                inventory_data = json.load(f)
        except FileNotFoundError:
            print("No inventory export file found - skipping inventory startup")
            return

        densities = get_density_reference()
        
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
                storage_unit=item.get('storage_unit', '')
            )

            # Apply density and category from reference data
            name_lower = new_item.name.lower()
            if name_lower in densities:
                new_item.density = densities[name_lower]["density_g_per_ml"]
                cat_name = densities[name_lower]["category"]
                category = IngredientCategory.query.filter_by(name=cat_name).first()
                if category:
                    new_item.category_id = category.id

            db.session.add(new_item)
            db.session.flush()

            # Create initial FIFO history entry for existing quantities
            if new_item.quantity > 0:
                history = InventoryHistory(
                    inventory_item_id=new_item.id,
                    change_type='restock',
                    quantity_change=new_item.quantity,
                    remaining_quantity=new_item.quantity,
                    unit_cost=new_item.cost_per_unit,
                    source='Startup Data',
                    created_by=1,
                    quantity_used=0,
                    note='Initial startup inventory',
                    is_perishable=new_item.is_perishable,
                    expiration_date=new_item.expiration_date,
                    shelf_life_days=None
                )
                db.session.add(history)
                print(f'[FIFO] Created initial entry for {new_item.quantity} {new_item.unit}')

            density_str = f' (density: {new_item.density} g/ml)' if new_item.density else ''
            print(f'[ADDED] {new_item.name} → {new_item.quantity} {new_item.unit}{density_str}')

        db.session.commit()
        print("✅ Startup inventory service complete")

if __name__ == '__main__':
    load_startup_inventory()
from app import app, db
from models import InventoryItem, IngredientCategory, InventoryHistory
import json

def get_density_reference():
    """Load density reference data for categorizing ingredients"""
    try:
        with open('data/density_reference.json', 'r') as f:
            data = json.load(f)
            return {item['name'].lower(): item for item in data['common_densities']}
    except FileNotFoundError:
        return {}

def load_startup_inventory():
    """Load startup inventory items with FIFO history tracking"""
    with app.app_context():
        try:
            with open('inventory_export_20250502_225444.json', 'r') as f:
                inventory_data = json.load(f)
        except FileNotFoundError:
            print("No inventory export file found - skipping inventory startup")
            return

        print("Loading startup inventory...")
        densities = get_density_reference()
        
        for item in inventory_data:
            existing = InventoryItem.query.filter_by(name=item['name']).first()
            if existing:
                print(f"[SKIPPED] {item['name']} already exists.")
                continue

            new_item = InventoryItem(
                name=item['name'],
                quantity=float(item.get('quantity', 0.0)),
                unit=item.get('unit', ''),
                type=item.get('type', 'ingredient'),
                cost_per_unit=float(item.get('cost_per_unit', 0.0)),
                intermediate=bool(item.get('intermediate', False)),
                low_stock_threshold=float(item.get('low_stock_threshold', 0.0)),
                storage_amount=float(item.get('storage_amount', 0.0)),
                storage_unit=item.get('storage_unit', '')
            )

            # Apply density and category from reference data
            name_lower = new_item.name.lower()
            if name_lower in densities:
                new_item.density = densities[name_lower]["density_g_per_ml"]
                cat_name = densities[name_lower]["category"]
                category = IngredientCategory.query.filter_by(name=cat_name).first()
                if category:
                    new_item.category_id = category.id

            db.session.add(new_item)
            db.session.flush()

            # Create initial FIFO history entry for existing quantities
            if new_item.quantity > 0:
                history = InventoryHistory(
                    inventory_item_id=new_item.id,
                    change_type='restock',
                    quantity_change=new_item.quantity,
                    remaining_quantity=new_item.quantity,
                    unit=new_item.unit,
                    unit_cost=new_item.cost_per_unit,
                    source='Startup Data',
                    created_by=1,
                    quantity_used=0,
                    note='Initial startup inventory'
                )
                db.session.add(history)
                print(f'[FIFO] Created initial entry for {new_item.quantity} {new_item.unit}')

            density_str = f' (density: {new_item.density} g/ml)' if new_item.density else ''
            print(f'[ADDED] {new_item.name} → {new_item.quantity} {new_item.unit}{density_str}')

        db.session.commit()
        print("✅ Startup inventory service complete")

if __name__ == '__main__':
    load_startup_inventory()
