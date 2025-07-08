
#!/usr/bin/env python3
"""
Cleanup script to fix FIFO entries that have remaining quantities when they shouldn't
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from app import create_app
from app.models import db, InventoryHistory
from app.models.product import ProductSKUHistory

def cleanup_broken_fifo_entries():
    """Fix entries that have remaining quantities but represent deductions"""
    app = create_app()
    
    with app.app_context():
        print("=== FIFO Cleanup Script ===")
        
        # Fix InventoryHistory entries (raw ingredients/containers)
        print("\n1. Fixing InventoryHistory deduction entries...")
        broken_inventory_entries = InventoryHistory.query.filter(
            InventoryHistory.quantity_change < 0,
            InventoryHistory.remaining_quantity != None
        ).all()
        
        print(f"Found {len(broken_inventory_entries)} broken InventoryHistory entries")
        
        for entry in broken_inventory_entries:
            print(f"  Fixing entry {entry.id}: {entry.change_type} {entry.quantity_change} (was remaining: {entry.remaining_quantity})")
            entry.remaining_quantity = None
        
        # Fix ProductSKUHistory entries (products)
        print("\n2. Fixing ProductSKUHistory deduction entries...")
        broken_product_entries = ProductSKUHistory.query.filter(
            ProductSKUHistory.quantity_change < 0,
            ProductSKUHistory.remaining_quantity != None
        ).all()
        
        print(f"Found {len(broken_product_entries)} broken ProductSKUHistory entries")
        
        for entry in broken_product_entries:
            print(f"  Fixing entry {entry.id}: {entry.change_type} {entry.quantity_change} (was remaining: {entry.remaining_quantity})")
            entry.remaining_quantity = None
        
        # Fix non-lot entries (credits, adjustments, etc.) that should also be None
        print("\n3. Fixing non-lot entries that should have None remaining...")
        
        # InventoryHistory non-lot entries
        non_lot_inventory = InventoryHistory.query.filter(
            InventoryHistory.fifo_reference_id != None,  # These reference other entries
            InventoryHistory.remaining_quantity != None
        ).all()
        
        print(f"Found {len(non_lot_inventory)} non-lot InventoryHistory entries")
        
        for entry in non_lot_inventory:
            print(f"  Fixing entry {entry.id}: {entry.change_type} with fifo_reference_id {entry.fifo_reference_id}")
            entry.remaining_quantity = None
        
        # ProductSKUHistory non-lot entries  
        non_lot_product = ProductSKUHistory.query.filter(
            ProductSKUHistory.fifo_reference_id != None,  # These reference other entries
            ProductSKUHistory.remaining_quantity != None
        ).all()
        
        print(f"Found {len(non_lot_product)} non-lot ProductSKUHistory entries")
        
        for entry in non_lot_product:
            print(f"  Fixing entry {entry.id}: {entry.change_type} with fifo_reference_id {entry.fifo_reference_id}")
            entry.remaining_quantity = None
        
        # Commit all changes
        total_fixed = len(broken_inventory_entries) + len(broken_product_entries) + len(non_lot_inventory) + len(non_lot_product)
        
        if total_fixed > 0:
            db.session.commit()
            print(f"\n✅ Successfully fixed {total_fixed} FIFO entries")
        else:
            print("\n✅ No broken entries found!")
        
        # Verification
        print("\n3. Verification...")
        remaining_broken_inventory = InventoryHistory.query.filter(
            InventoryHistory.quantity_change < 0,
            InventoryHistory.remaining_quantity != None
        ).count()
        
        remaining_broken_product = ProductSKUHistory.query.filter(
            ProductSKUHistory.quantity_change < 0,
            ProductSKUHistory.remaining_quantity != None
        ).count()
        
        if remaining_broken_inventory == 0 and remaining_broken_product == 0:
            print("✅ All broken FIFO entries have been fixed!")
        else:
            print(f"❌ Still have {remaining_broken_inventory} broken inventory + {remaining_broken_product} broken product entries")
        
        print("\n🎉 FIFO cleanup completed successfully!")

if __name__ == "__main__":
    cleanup_broken_fifo_entries()
