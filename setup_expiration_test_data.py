
#!/usr/bin/env python3
"""
Script to set up test expiration data for debugging
"""

from app import create_app, db
from app.models import InventoryItem, ProductSKU, ProductSKUHistory
from flask_login import current_user

def setup_expiration_data():
    """Set up expiration data for existing products"""
    
    app = create_app()
    with app.app_context():
        print("Setting up expiration test data...")
        
        # Get all inventory items that are used in products
        inventory_items = db.session.query(InventoryItem).join(
            ProductSKU, InventoryItem.id == ProductSKU.inventory_item_id
        ).distinct().all()
        
        print(f"Found {len(inventory_items)} inventory items linked to products")
        
        updated_count = 0
        for item in inventory_items:
            print(f"Checking item: {item.name} (ID: {item.id})")
            print(f"  Current: is_perishable={item.is_perishable}, shelf_life_days={item.shelf_life_days}")
            
            # Set some reasonable defaults for testing
            if not item.is_perishable:
                item.is_perishable = True
                item.shelf_life_days = 30  # 30 days default
                updated_count += 1
                print(f"  Updated to: is_perishable=True, shelf_life_days=30")
        
        if updated_count > 0:
            db.session.commit()
            print(f"\nUpdated {updated_count} inventory items with expiration data")
        else:
            print("\nNo items needed updating")
        
        # Check SKU history entries
        sku_entries = ProductSKUHistory.query.filter(
            ProductSKUHistory.remaining_quantity > 0
        ).all()
        
        print(f"\nFound {len(sku_entries)} SKU history entries with remaining quantity")
        
        perishable_entries = 0
        for entry in sku_entries:
            inventory_item = InventoryItem.query.get(entry.inventory_item_id)
            if inventory_item and inventory_item.is_perishable:
                perishable_entries += 1
        
        print(f"  {perishable_entries} are now marked as perishable")
        print(f"  {len(sku_entries) - perishable_entries} are non-perishable")

if __name__ == "__main__":
    setup_expiration_data()
