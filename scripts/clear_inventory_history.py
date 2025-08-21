
#!/usr/bin/env python3
"""
Script to clear inventory history and reset item quantities to zero.
This is useful for testing and debugging the inventory adjustment system.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.models import db, InventoryItem, UnifiedInventoryHistory
from app.models.inventory_lot import InventoryLot
import logging

def clear_inventory_history():
    """Clear all inventory history and reset item quantities to zero"""
    
    app = create_app()
    
    with app.app_context():
        try:
            print("🧹 Starting inventory history cleanup...")
            
            # Get counts before deletion
            history_count = UnifiedInventoryHistory.query.count()
            lot_count = InventoryLot.query.count()
            item_count = InventoryItem.query.count()
            
            print(f"📊 Current state:")
            print(f"   - Inventory items: {item_count}")
            print(f"   - History entries: {history_count}")
            print(f"   - FIFO lots: {lot_count}")
            
            # Clear all history entries
            if history_count > 0:
                print(f"🗑️  Deleting {history_count} history entries...")
                UnifiedInventoryHistory.query.delete()
                print("   ✅ History entries cleared")
            
            # Clear all FIFO lots
            if lot_count > 0:
                print(f"🗑️  Deleting {lot_count} FIFO lots...")
                InventoryLot.query.delete()
                print("   ✅ FIFO lots cleared")
            
            # Reset all inventory item quantities to zero
            if item_count > 0:
                print(f"🔄 Resetting {item_count} inventory item quantities to zero...")
                items_updated = InventoryItem.query.update({
                    InventoryItem.quantity: 0.0
                })
                print(f"   ✅ {items_updated} item quantities reset to zero")
            
            # Commit all changes
            db.session.commit()
            print("💾 All changes committed successfully!")
            
            # Verify cleanup
            final_history = UnifiedInventoryHistory.query.count()
            final_lots = InventoryLot.query.count()
            final_items = InventoryItem.query.filter(InventoryItem.quantity != 0).count()
            
            print(f"\n✅ Cleanup complete:")
            print(f"   - History entries remaining: {final_history}")
            print(f"   - FIFO lots remaining: {final_lots}")
            print(f"   - Items with non-zero quantity: {final_items}")
            
            if final_history == 0 and final_lots == 0 and final_items == 0:
                print("🎉 Perfect! All inventory data cleared successfully.")
                print("   You can now test fresh inventory adjustments.")
            else:
                print("⚠️  Some data may not have been cleared completely.")
                
        except Exception as e:
            print(f"❌ Error during cleanup: {str(e)}")
            db.session.rollback()
            return False
            
    return True

def clear_specific_item(item_id):
    """Clear history for a specific inventory item"""
    
    app = create_app()
    
    with app.app_context():
        try:
            item = InventoryItem.query.get(item_id)
            if not item:
                print(f"❌ Item with ID {item_id} not found")
                return False
                
            print(f"🧹 Clearing history for item: {item.name} (ID: {item_id})")
            
            # Count entries before deletion
            history_count = UnifiedInventoryHistory.query.filter_by(inventory_item_id=item_id).count()
            lot_count = InventoryLot.query.filter_by(inventory_item_id=item_id).count()
            
            print(f"📊 Item has {history_count} history entries and {lot_count} FIFO lots")
            
            # Clear history for this item
            UnifiedInventoryHistory.query.filter_by(inventory_item_id=item_id).delete()
            print("   ✅ History entries cleared")
            
            # Clear FIFO lots for this item
            InventoryLot.query.filter_by(inventory_item_id=item_id).delete()
            print("   ✅ FIFO lots cleared")
            
            # Reset item quantity to zero
            item.quantity = 0.0
            print("   ✅ Item quantity reset to zero")
            
            db.session.commit()
            print(f"💾 Changes committed for {item.name}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error clearing item {item_id}: {str(e)}")
            db.session.rollback()
            return False

def show_current_state():
    """Show current state of inventory system"""
    
    app = create_app()
    
    with app.app_context():
        print("📊 Current Inventory System State:")
        print("=" * 50)
        
        # Show items with quantities
        items = InventoryItem.query.all()
        for item in items:
            history_count = UnifiedInventoryHistory.query.filter_by(inventory_item_id=item.id).count()
            lot_count = InventoryLot.query.filter_by(inventory_item_id=item.id).count()
            fifo_total = sum(lot.remaining_quantity for lot in InventoryLot.query.filter_by(inventory_item_id=item.id).all())
            
            print(f"Item: {item.name} (ID: {item.id})")
            print(f"   Quantity: {item.quantity}")
            print(f"   FIFO Total: {fifo_total}")
            print(f"   History Entries: {history_count}")
            print(f"   FIFO Lots: {lot_count}")
            print(f"   Sync Status: {'✅ OK' if item.quantity == fifo_total else '❌ MISMATCH'}")
            print()

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Clear inventory history for testing')
    parser.add_argument('--item-id', type=int, help='Clear history for specific item ID only')
    parser.add_argument('--show-state', action='store_true', help='Show current state without clearing')
    parser.add_argument('--clear-all', action='store_true', help='Clear all inventory history')
    
    args = parser.parse_args()
    
    if args.show_state:
        show_current_state()
    elif args.item_id:
        clear_specific_item(args.item_id)
    elif args.clear_all:
        print("⚠️  This will clear ALL inventory history and reset all quantities to zero!")
        confirm = input("Are you sure? Type 'yes' to continue: ")
        if confirm.lower() == 'yes':
            clear_inventory_history()
        else:
            print("❌ Operation cancelled")
    else:
        print("Usage examples:")
        print("  python scripts/clear_inventory_history.py --show-state")
        print("  python scripts/clear_inventory_history.py --item-id 2")
        print("  python scripts/clear_inventory_history.py --clear-all")
