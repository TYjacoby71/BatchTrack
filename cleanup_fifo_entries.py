
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
            InventoryHistory.remaining_quantity > 0
        ).all()
        
        print(f"Found {len(broken_inventory_entries)} broken InventoryHistory entries")
        
        for entry in broken_inventory_entries:
            print(f"  Fixing entry {entry.id}: {entry.change_type} {entry.quantity_change} (was remaining: {entry.remaining_quantity})")
            entry.remaining_quantity = 0.0
        
        # Fix ProductSKUHistory entries (products)
        print("\n2. Fixing ProductSKUHistory deduction entries...")
        broken_product_entries = ProductSKUHistory.query.filter(
            ProductSKUHistory.quantity_change < 0,
            ProductSKUHistory.remaining_quantity > 0
        ).all()
        
        print(f"Found {len(broken_product_entries)} broken ProductSKUHistory entries")
        
        for entry in broken_product_entries:
            print(f"  Fixing entry {entry.id}: {entry.change_type} {entry.quantity_change} (was remaining: {entry.remaining_quantity})")
            entry.remaining_quantity = 0.0
        
        # Commit the fixes
        try:
            db.session.commit()
            print(f"\n✅ Successfully fixed {len(broken_inventory_entries) + len(broken_product_entries)} FIFO entries")
            
            # Verify the fix
            print("\n3. Verification...")
            remaining_broken_inventory = InventoryHistory.query.filter(
                InventoryHistory.quantity_change < 0,
                InventoryHistory.remaining_quantity > 0
            ).count()
            
            remaining_broken_product = ProductSKUHistory.query.filter(
                ProductSKUHistory.quantity_change < 0,
                ProductSKUHistory.remaining_quantity > 0
            ).count()
            
            if remaining_broken_inventory == 0 and remaining_broken_product == 0:
                print("✅ All broken FIFO entries have been fixed!")
            else:
                print(f"⚠️  Still have {remaining_broken_inventory} inventory + {remaining_broken_product} product broken entries")
                
        except Exception as e:
            print(f"❌ Error committing changes: {e}")
            db.session.rollback()
            return False
            
        return True

if __name__ == "__main__":
    success = cleanup_broken_fifo_entries()
    if success:
        print("\n🎉 FIFO cleanup completed successfully!")
    else:
        print("\n💥 FIFO cleanup failed!")
        sys.exit(1)
