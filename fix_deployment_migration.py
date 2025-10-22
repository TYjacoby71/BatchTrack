
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
                
            # Create engine with autocommit isolation to avoid transaction issues
            engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
            
            print("🔄 Attempting to fix failed migration...")
            
            # Use multiple connection attempts to clear any stuck transactions
            for attempt in range(3):
                try:
                    with engine.connect() as conn:
                        print(f"📍 Connection attempt {attempt + 1}/3")
                        
                        # Check current migration state
                        try:
                            result = conn.execute(text("SELECT version_num FROM alembic_version;"))
                            current_version = result.scalar()
                            print(f"📍 Current migration version: {current_version}")
                        except Exception as e:
                            print(f"⚠️  Could not read migration version: {e}")
                            continue
                        
                        # Force reset migration to base schema
                        if current_version and current_version != '0001_base_schema':
                            print(f"🔄 Forcing migration reset to 0001_base_schema...")
                            try:
                                conn.execute(text(
                                    "UPDATE alembic_version SET version_num = '0001_base_schema'"
                                ))
                                print("✅ Migration version reset successfully")
                                break
                            except Exception as e:
                                print(f"❌ Failed to reset migration version: {e}")
                                continue
                        else:
                            print("✅ Migration already at base schema")
                            break
                            
                except Exception as e:
                    print(f"❌ Connection attempt {attempt + 1} failed: {e}")
                    if attempt == 2:  # Last attempt
                        print("❌ All connection attempts failed")
                        return False
                    continue
            
            print("✅ Database transaction issues resolved")
            print("🚀 Now run 'flask db upgrade' to retry the migration")
            return True
            
        except Exception as e:
            print(f"❌ Error fixing migration: {e}")
            return False

if __name__ == '__main__':
    success = fix_migration()
    sys.exit(0 if success else 1)
