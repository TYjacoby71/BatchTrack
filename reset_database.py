
#!/usr/bin/env python3
"""
Reset database to clean state and rerun migrations
"""

import os
import sys
from sqlalchemy import create_engine, text
from app import create_app

def reset_database():
    """Reset database and run migrations"""
    app = create_app()
    
    with app.app_context():
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            print("❌ No DATABASE_URL found")
            return False
            
        print(f"🔧 Resetting database: {database_url[:50]}...")
        
        try:
            engine = create_engine(database_url)
            
            # For PostgreSQL, we need to handle the transaction state
            if 'postgresql' in database_url.lower():
                with engine.connect() as conn:
                    # Roll back any pending transaction
                    print("   🔄 Rolling back pending transaction...")
                    conn.rollback()
                    
                    # Drop and recreate schema
                    print("   🗑️  Dropping and recreating schema...")
                    conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
                    conn.execute(text("CREATE SCHEMA public"))
                    conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
                    conn.commit()
                    
            elif 'sqlite' in database_url.lower():
                # For SQLite, just remove the file
                db_path = database_url.replace('sqlite:///', '')
                if os.path.exists(db_path):
                    os.remove(db_path)
                    print(f"   🗑️  Removed SQLite database: {db_path}")
                    
            print("   ✅ Database reset complete")
            return True
            
        except Exception as e:
            print(f"   ❌ Error resetting database: {e}")
            return False

def run_migrations():
    """Run flask db upgrade"""
    try:
        print("   🔄 Running migrations...")
        result = os.system("flask db upgrade")
        if result == 0:
            print("   ✅ Migrations completed successfully")
            return True
        else:
            print("   ❌ Migration failed")
            return False
    except Exception as e:
        print(f"   ❌ Error running migrations: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting database reset...")
    
    if reset_database():
        if run_migrations():
            print("🎉 Database reset and migration completed successfully!")
            sys.exit(0)
        else:
            print("❌ Migration failed after database reset")
            sys.exit(1)
    else:
        print("❌ Database reset failed")
        sys.exit(1)
