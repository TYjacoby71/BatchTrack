
import json
from app import app, db
from models import InventoryItem

# Path to your legacy inventory export
JSON_PATH = 'inventory_export_20250430_235506.json'

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
                storage_unit=item.get('storage_unit', '')
            )
            db.session.add(new_item)
            print(f"[ADDED] {new_item.name} → {new_item.quantity} {new_item.unit}")

        db.session.commit()
        print("✅ Legacy inventory import complete.")

if __name__ == '__main__':
    load_legacy_inventory()
