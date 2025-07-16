
#!/usr/bin/env python3
"""
Script to clear all FIFO history for a specific raw inventory item (ingredients/containers)
"""

from app import create_app, db
from app.models import InventoryItem, InventoryHistory

def clear_inventory_history(inventory_item_id):
    """Clear all history entries for a specific inventory item"""
    
    app = create_app()
    with app.app_context():
        print(f"Starting cleanup for inventory item {inventory_item_id}...")
        
        # Get the inventory item
        item = InventoryItem.query.get(inventory_item_id)
        if not item:
            print(f"Inventory item with ID {inventory_item_id} not found")
            return
        
        print(f"Found item: {item.name}")
        print(f"Current quantity: {item.quantity}")
        print(f"Item type: {item.type}")
        
        # Get all history entries
        history_entries = InventoryHistory.query.filter_by(
            inventory_item_id=inventory_item_id
        ).all()
        
        print(f"Found {len(history_entries)} history entries")
        
        # Show breakdown by change type
        change_types = {}
        for entry in history_entries:
            change_types[entry.change_type] = change_types.get(entry.change_type, 0) + 1
        
        print("History breakdown by change type:")
        for change_type, count in change_types.items():
            print(f"  {change_type}: {count} entries")
        
        # Delete all history entries
        for entry in history_entries:
            db.session.delete(entry)
        
        # Reset the inventory item quantity to 0
        item.quantity = 0.0
        print("Reset inventory quantity to 0.0")
        
        # Commit changes
        db.session.commit()
        print(f"Successfully cleared {len(history_entries)} history entries for inventory item {inventory_item_id}")

def list_inventory_items():
    """List all inventory items with their IDs for reference"""
    
    app = create_app()
    with app.app_context():
        print("=== Available Inventory Items ===")
        
        items = InventoryItem.query.filter_by(is_active=True).order_by(InventoryItem.name).all()
        
        for item in items:
            history_count = InventoryHistory.query.filter_by(inventory_item_id=item.id).count()
            print(f"ID: {item.id:3d} | {item.name:30s} | Type: {item.type:12s} | Qty: {item.quantity:8.2f} {item.unit:6s} | History: {history_count} entries")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "list":
            list_inventory_items()
        else:
            try:
                inventory_id = int(sys.argv[1])
                clear_inventory_history(inventory_id)
            except ValueError:
                print("Usage: python cleanup_raw_inventory_history.py <inventory_item_id>")
                print("   or: python cleanup_raw_inventory_history.py list")
    else:
        print("Usage: python cleanup_raw_inventory_history.py <inventory_item_id>")
        print("   or: python cleanup_raw_inventory_history.py list")
        print("\nExample:")
        print("  python cleanup_raw_inventory_history.py list  # Show all items")
        print("  python cleanup_raw_inventory_history.py 1     # Clear history for item ID 1")
