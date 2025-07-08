
#!/usr/bin/env python3
"""
Script to clear all FIFO history for a specific SKU
"""

from app import create_app, db
from app.models.product import ProductSKU, ProductSKUHistory
from app.models import InventoryItem
from flask_login import current_user

def clear_sku_history(sku_id):
    """Clear all history entries for a specific SKU"""
    
    app = create_app()
    with app.app_context():
        print(f"Starting cleanup for SKU {sku_id}...")
        
        # Get the SKU
        sku = ProductSKU.query.filter_by(inventory_item_id=sku_id).first()
        if not sku:
            print(f"SKU with inventory_item_id {sku_id} not found")
            return
        
        print(f"Found SKU: {sku.display_name}")
        print(f"Current quantity: {sku.quantity}")
        
        # Get all history entries
        history_entries = ProductSKUHistory.query.filter_by(
            inventory_item_id=sku_id
        ).all()
        
        print(f"Found {len(history_entries)} history entries")
        
        # Delete all history entries
        for entry in history_entries:
            db.session.delete(entry)
        
        # Reset the inventory item quantity to 0
        if sku.inventory_item:
            sku.inventory_item.quantity = 0.0
            print("Reset inventory quantity to 0.0")
        
        # Commit changes
        db.session.commit()
        print(f"Successfully cleared {len(history_entries)} history entries for SKU {sku_id}")

if __name__ == "__main__":
    # Clear SKU 4 (Admin Apple Sauce - Base - Bulk)
    clear_sku_history(4)
