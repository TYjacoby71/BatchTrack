
#!/usr/bin/env python3
"""
Script to fix expiration times that show 00:00:00
"""
import sqlite3
import os
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
        
        # Find entries with expiration_date but time component is 00:00:00
        print("🔍 Finding entries with 00:00:00 expiration times...")
        cursor.execute("""
            SELECT id, inventory_item_id, expiration_date, timestamp, shelf_life_days
            FROM inventory_history 
            WHERE expiration_date IS NOT NULL 
            AND time(expiration_date) = '00:00:00'
            AND remaining_quantity > 0
        """)
        
        entries_to_fix = cursor.fetchall()
        
        if not entries_to_fix:
            print("✅ No entries found with 00:00:00 expiration times")
            return True
        
        print(f"🔧 Found {len(entries_to_fix)} entries to fix")
        
        fixed_count = 0
        for entry_id, item_id, exp_date, timestamp, shelf_life in entries_to_fix:
            try:
                # Parse the current expiration date
                exp_datetime = datetime.fromisoformat(exp_date.replace('Z', '+00:00'))
                
                # If the time is exactly 00:00:00, recalculate based on timestamp + shelf_life
                if exp_datetime.time() == datetime.min.time():
                    if timestamp and shelf_life:
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
                        print(f"✅ Fixed entry {entry_id}: {exp_date} -> {new_expiration.isoformat()}")
                    else:
                        print(f"⚠️  Skipping entry {entry_id}: missing timestamp or shelf_life")
                        
            except Exception as e:
                print(f"❌ Error fixing entry {entry_id}: {e}")
                continue
        
        conn.commit()
        print(f"\n🎉 Successfully fixed {fixed_count} expiration times!")
        
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
        print("\n✅ Expiration times fixed successfully!")
        print("You may need to refresh the expiration alerts page to see the changes.")
    else:
        print("\n💥 Failed to fix expiration times!")
