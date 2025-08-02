
#!/usr/bin/env python3
"""
Clear only developer users from the database
This removes developer users and their role assignments while preserving customer users
"""

from app import create_app
from app.extensions import db
from app.models import User, UserRoleAssignment
from app.models.user_preferences import UserPreferences

def clear_developer_users():
    """Clear only developer users and their assignments"""
    app = create_app()
    
    with app.app_context():
        print("=== Clearing Developer Users Only ===")
        print("⚠️  This will remove ALL developer users and their role assignments!")
        print("ℹ️  Customer users and organizations will be preserved")
        
        # Show current developer users
        dev_users = User.query.filter_by(user_type='developer').all()
        if not dev_users:
            print("ℹ️  No developer users found")
            return
        
        print(f"📋 Found {len(dev_users)} developer users:")
        for user in dev_users:
            print(f"   - {user.username} ({user.email})")
        
        confirmation = input("Type 'CLEAR DEVS' to confirm: ")
        if confirmation != 'CLEAR DEVS':
            print("❌ Operation cancelled")
            return
        
        try:
            # Get developer user IDs for role assignment cleanup
            dev_user_ids = [user.id for user in dev_users]
            
            # Clear developer role assignments
            print("🗑️  Clearing developer role assignments...")
            assignments_deleted = UserRoleAssignment.query.filter(
                UserRoleAssignment.user_id.in_(dev_user_ids)
            ).delete(synchronize_session=False)
            
            # Clear developer user preferences
            print("🗑️  Clearing developer user preferences...")
            prefs_deleted = UserPreferences.query.filter(
                UserPreferences.user_id.in_(dev_user_ids)
            ).delete(synchronize_session=False)
            
            # Clear developer users
            print("🗑️  Clearing developer users...")
            users_deleted = User.query.filter_by(user_type='developer').delete()
            
            # Commit changes
            db.session.commit()
            
            print("✅ Developer users cleared successfully!")
            print(f"   - Removed {users_deleted} developer users")
            print(f"   - Removed {assignments_deleted} role assignments")
            print(f"   - Removed {prefs_deleted} user preferences")
            print("👥 Customer users and organizations preserved")
            print("🔄 Run 'flask seed-users' to recreate developer user")
            
        except Exception as e:
            print(f"❌ Error clearing developer users: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    clear_developer_users()
