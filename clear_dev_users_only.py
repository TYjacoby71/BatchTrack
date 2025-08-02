
#!/usr/bin/env python3
"""
Clear Developer Users Only - PostgreSQL Safe
Removes only developer users and their related data while preserving customer users.
Handles foreign key constraints in proper dependency order.
"""

import sys
from app import create_app
from app.extensions import db
from app.models.models import User
from app.models.user_role_assignment import UserRoleAssignment
from app.models.user_preferences import UserPreferences

def clear_developer_users():
    """Clear only developer users and their assignments while preserving customers"""
    
    print("⚠️  This removes all DEVELOPER users and their role assignments")
    print("✅ Customer users and organizations will be preserved")
    print("✅ Schema (permissions, roles, tiers) will be preserved")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Show current developer users
            dev_users = User.query.filter_by(user_type='developer').all()
            if not dev_users:
                print("ℹ️  No developer users found")
                return True
            
            print(f"📋 Found {len(dev_users)} developer users:")
            for user in dev_users:
                print(f"   - {user.username} ({user.email})")
            
            confirmation = input("Type 'CLEAR DEVS' to confirm: ")
            if confirmation != 'CLEAR DEVS':
                print("❌ Operation cancelled")
                return False
            
            # Get developer user IDs for efficient bulk operations
            dev_user_ids = [user.id for user in dev_users]
            
            # Step 1: Clear developer user preferences (foreign key to user)
            print("🗑️  Clearing developer user preferences...")
            if dev_user_ids:
                db.session.execute(db.text("DELETE FROM user_preferences WHERE user_id = ANY(:user_ids)"), {"user_ids": dev_user_ids})
            
            # Step 2: Clear developer user role assignments
            print("🗑️  Clearing developer role assignments...")
            if dev_user_ids:
                db.session.execute(db.text("DELETE FROM user_role_assignment WHERE user_id = ANY(:user_ids)"), {"user_ids": dev_user_ids})
            
            # Step 3: Clear any other tables that might reference developer users
            print("🗑️  Clearing other developer user-related data...")
            
            # Check for tables that might reference users
            tables_to_check = [
                'batch', 'recipe', 'inventory_item', 'inventory_history', 
                'product', 'product_sku', 'reservation'
            ]
            
            for table in tables_to_check:
                # Check if table exists and has user-related columns
                result = db.session.execute(db.text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = :table_name 
                    AND column_name IN ('created_by', 'updated_by', 'assigned_by', 'deleted_by')
                """), {"table_name": table}).fetchall()
                
                if result:
                    print(f"   Clearing {table} developer user references...")
                    for column in result:
                        col_name = column[0]
                        if dev_user_ids:
                            # Set references to NULL instead of deleting records (preserve data)
                            db.session.execute(db.text(f"UPDATE {table} SET {col_name} = NULL WHERE {col_name} = ANY(:user_ids)"), {"user_ids": dev_user_ids})
            
            # Step 4: Clear developer users
            print("🗑️  Clearing developer users...")
            users_deleted = len(dev_user_ids)
            db.session.execute(db.text("DELETE FROM \"user\" WHERE user_type = 'developer'"))
            
            # Commit all changes
            db.session.commit()
            
            print("✅ Developer users cleared successfully!")
            print(f"   - Removed {users_deleted} developer users")
            print("👥 Customer users and organizations preserved")
            print("🔄 Run 'flask seed-users' to recreate developer user")
            
            # Summary
            remaining_users = User.query.count()
            remaining_devs = User.query.filter_by(user_type='developer').count()
            print(f"\n📊 Summary:")
            print(f"Remaining users: {remaining_users} (should be customers only)")
            print(f"Remaining developers: {remaining_devs} (should be 0)")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error clearing developer users: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            return False
    
    return True

if __name__ == '__main__':
    clear_developer_users()
