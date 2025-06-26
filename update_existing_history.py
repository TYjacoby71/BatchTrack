
#!/usr/bin/env python3
"""
Update existing inventory history records with default POS integration values
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, InventoryHistory, InventoryItem

def update_existing_records():
    app = create_app()
    
    with app.app_context():
        # Update existing inventory_history records
        history_records = InventoryHistory.query.all()
        print(f"Updating {len(history_records)} inventory history records...")
        
        for record in history_records:
            if not hasattr(record, 'is_reserved') or record.is_reserved is None:
                record.is_reserved = False
        
        # Update existing inventory_item records
        inventory_items = InventoryItem.query.all()
        print(f"Updating {len(inventory_items)} inventory items...")
        
        for item in inventory_items:
            if not hasattr(item, 'frozen_quantity') or item.frozen_quantity is None:
                item.frozen_quantity = 0.0
            if not hasattr(item, 'available_quantity') or item.available_quantity is None:
                item.available_quantity = item.quantity
        
        db.session.commit()
        print("Update complete!")

if __name__ == '__main__':
    update_existing_records()
