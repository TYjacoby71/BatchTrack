
#!/usr/bin/env python3
"""
Script to add missing timezone column to user table
"""
import sqlite3
import os
from pathlib import Path

def add_timezone_column():
    """Add the missing timezone column to the user table"""
    db_path = Path("instance/batchtrack.db")
    
    if not db_path.exists():
        print("❌ Database file not found!")
        return False
    
    print(f"📂 Found database at: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if timezone column exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'timezone' in columns:
            print("✅ Timezone column already exists!")
            return True
        
        # Add the timezone column
        print("➕ Adding timezone column...")
        cursor.execute("ALTER TABLE user ADD COLUMN timezone VARCHAR(64) DEFAULT 'America/New_York'")
        
        # Update existing users to have the default timezone
        cursor.execute("UPDATE user SET timezone = 'America/New_York' WHERE timezone IS NULL")
        
        conn.commit()
        
        print("✅ Successfully added timezone column to user table")
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
    print("🔧 Adding missing timezone column to user table...")
    if add_timezone_column():
        print("\n🎉 Timezone column added successfully!")
        print("You can now restart your Flask app.")
    else:
        print("\n💥 Failed to add timezone column!")
