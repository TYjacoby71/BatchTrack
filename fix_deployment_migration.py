
#!/usr/bin/env python3
"""
Fix deployment migration issue by resetting transaction and retrying
"""
import os
import sys
from sqlalchemy import create_engine, text
from app import create_app

def fix_migration():
    """Reset failed transaction and retry migration"""
    app = create_app()
    
    with app.app_context():
        try:
            # Get database URL from environment
            database_url = (
                os.environ.get('DATABASE_INTERNAL_URL') or 
                os.environ.get('DATABASE_URL') or
                app.config.get('SQLALCHEMY_DATABASE_URI')
            )
            
            if not database_url:
                print("❌ No database URL found")
                return False
                
            # Create engine
            engine = create_engine(database_url)
            
            print("🔄 Attempting to fix failed migration...")
            
            with engine.connect() as conn:
                # First, try to end any existing transaction
                try:
                    # Try to rollback first
                    conn.execute(text("ROLLBACK;"))
                    print("✅ Rolled back failed transaction")
                except Exception as e:
                    print(f"ℹ️  No active transaction to rollback: {e}")
                
                # Create a fresh transaction to check migration state
                trans = conn.begin()
                try:
                    result = conn.execute(text("SELECT version_num FROM alembic_version;"))
                    current_version = result.scalar()
                    print(f"📍 Current migration version: {current_version}")
                    
                    # Also check if feature_flag table exists
                    result = conn.execute(text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'feature_flag'
                        );
                    """))
                    table_exists = result.scalar()
                    print(f"📍 feature_flag table exists: {table_exists}")
                    
                    trans.commit()
                except Exception as e:
                    trans.rollback()
                    print(f"❌ Error checking migration state: {e}")
                    return False
                
            print("✅ Database transaction reset successfully")
            print("🚀 Now run 'flask db upgrade' to retry the migration")
            return True
            
        except Exception as e:
            print(f"❌ Error fixing migration: {e}")
            return False

if __name__ == '__main__':
    success = fix_migration()
    sys.exit(0 if success else 1)
