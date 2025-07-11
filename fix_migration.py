
#!/usr/bin/env python3
"""
Script to manually fix the migration issues
"""
import sqlite3
import os
from pathlib import Path

def fix_migration_manually():
    """Fix the migration by dropping temp table and updating version"""
    # Try common database locations
    possible_paths = [
        "instance/database.db",
        "database.db",
        "app.db"
    ]
    
    db_path = None
    for path in possible_paths:
        if Path(path).exists():
            db_path = path
            break
    
    if not db_path:
        print("❌ Database file not found!")
        return False
    
    print(f"📂 Found database at: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Drop the temporary table if it exists
        print("🗑️  Dropping temporary table...")
        cursor.execute("DROP TABLE IF EXISTS _alembic_tmp_user_preferences;")
        
        # Update alembic version to mark migration as complete
        print("📝 Updating migration version...")
        cursor.execute("UPDATE alembic_version SET version_num = 'f6a9b50d9a17';")
        
        conn.commit()
        
        # Verify the change
        cursor.execute("SELECT version_num FROM alembic_version;")
        version = cursor.fetchone()
        
        print(f"✅ Migration version updated to: {version[0] if version else 'None'}")
        
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
    print("🔧 Fixing migration manually...")
    if fix_migration_manually():
        print("\n🎉 Migration fixed successfully!")
        print("You can now run 'flask db current' to verify.")
    else:
        print("\n💥 Migration fix failed!")
