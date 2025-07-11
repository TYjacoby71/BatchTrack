
#!/usr/bin/env python3

import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta

def fix_expiration_times():
    """Fix expiration times that are showing 00:00:00"""
    db_path = Path("instance/batchtrack.db")
    
    if not db_path.exists():
        print("❌ Database file not found!")
        return False
    
    print(f"📂 Found database at: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Fix inventory_history entries
        print("🔍 Finding inventory entries with 00:00:00 expiration times...")
        cursor.execute("""
            SELECT id, inventory_item_id, expiration_date, timestamp, shelf_life_days
            FROM inventory_history 
            WHERE expiration_date IS NOT NULL 
            AND time(expiration_date) = '00:00:00'
            AND remaining_quantity > 0
            AND timestamp IS NOT NULL
            AND shelf_life_days IS NOT NULL
        """)
        
        inventory_entries = cursor.fetchall()
        
        if inventory_entries:
            print(f"🔧 Found {len(inventory_entries)} inventory entries to fix")
            
            fixed_count = 0
            for entry_id, item_id, exp_date, timestamp, shelf_life in inventory_entries:
                try:
                    # Parse timestamp
                    ts_datetime = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    
                    # Calculate new expiration with proper time
                    new_expiration = ts_datetime + timedelta(days=shelf_life)
                    
                    # Update the entry
                    cursor.execute("""
                        UPDATE inventory_history 
                        SET expiration_date = ?
                        WHERE id = ?
                    """, (new_expiration.isoformat(), entry_id))
                    
                    fixed_count += 1
                    print(f"✅ Fixed inventory entry {entry_id}: {exp_date} -> {new_expiration.strftime('%Y-%m-%d %H:%M:%S')}")
                        
                except Exception as e:
                    print(f"❌ Error fixing inventory entry {entry_id}: {e}")
                    continue
            
            print(f"🎉 Fixed {fixed_count} inventory expiration times!")
        else:
            print("✅ No inventory entries found with 00:00:00 expiration times")
        
        # Fix product_sku_history entries
        print("\n🔍 Finding product entries with 00:00:00 expiration times...")
        cursor.execute("""
            SELECT id, inventory_item_id, expiration_date, timestamp, shelf_life_days
            FROM product_sku_history 
            WHERE expiration_date IS NOT NULL 
            AND time(expiration_date) = '00:00:00'
            AND remaining_quantity > 0
            AND timestamp IS NOT NULL
            AND shelf_life_days IS NOT NULL
        """)
        
        product_entries = cursor.fetchall()
        
        if product_entries:
            print(f"🔧 Found {len(product_entries)} product entries to fix")
            
            product_fixed_count = 0
            for entry_id, item_id, exp_date, timestamp, shelf_life in product_entries:
                try:
                    # Parse timestamp
                    ts_datetime = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    
                    # Calculate new expiration with proper time
                    new_expiration = ts_datetime + timedelta(days=shelf_life)
                    
                    # Update the entry
                    cursor.execute("""
                        UPDATE product_sku_history 
                        SET expiration_date = ?
                        WHERE id = ?
                    """, (new_expiration.isoformat(), entry_id))
                    
                    product_fixed_count += 1
                    print(f"✅ Fixed product entry {entry_id}: {exp_date} -> {new_expiration.strftime('%Y-%m-%d %H:%M:%S')}")
                        
                except Exception as e:
                    print(f"❌ Error fixing product entry {entry_id}: {e}")
                    continue
            
            print(f"🎉 Fixed {product_fixed_count} product expiration times!")
        else:
            print("✅ No product entries found with 00:00:00 expiration times")
        
        conn.commit()
        print(f"\n🎉 Expiration times fixed successfully!")
        print("You may need to refresh the expiration alerts page to see the changes.")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ SQLite error: {e}")
        return False
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("🔧 Fixing expiration times...")
    if fix_expiration_times():
        sys.exit(0)
    else:
        print("💥 Migration fix failed!")
        sys.exit(1)
