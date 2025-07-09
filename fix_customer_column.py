
#!/usr/bin/env python3
"""
Script to fix missing customer column in reservation table
"""
import sqlite3
import os
from pathlib import Path

def fix_customer_column():
    """Add the missing customer column to the reservation table"""
    db_path = Path("instance/database.db")
    
    if not db_path.exists():
        print("Database file not found!")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if customer column exists
        cursor.execute("PRAGMA table_info(reservation)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'customer' in columns:
            print("Customer column already exists!")
            return True
        
        # Add the customer column
        cursor.execute("ALTER TABLE reservation ADD COLUMN customer VARCHAR(128)")
        conn.commit()
        
        print("✅ Successfully added customer column to reservation table")
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

def verify_fix():
    """Verify the fix worked"""
    db_path = Path("instance/database.db")
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check table structure
        cursor.execute("PRAGMA table_info(reservation)")
        columns = cursor.fetchall()
        
        print("\nCurrent reservation table structure:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Test a simple query
        cursor.execute("SELECT COUNT(*) FROM reservation")
        count = cursor.fetchone()[0]
        print(f"\nTotal reservations: {count}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Verification failed: {e}")
        return False
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("🔧 Fixing missing customer column in reservation table...")
    
    if fix_customer_column():
        print("\n🔍 Verifying fix...")
        verify_fix()
    else:
        print("❌ Fix failed!")
