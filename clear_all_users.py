
#!/usr/bin/env python3
"""
Clear all user data from the database while preserving schema
This removes all users, organizations, role assignments, and related data
"""

from app import create_app
from app.extensions import db
from app.models import (
    User, Organization, UserRoleAssignment, 
    UserStats, OrganizationStats, BillingSnapshot
)

def clear_all_user_data():
    """Clear all user-related data while preserving schema"""
    app = create_app()
    
    with app.app_context():
        print("=== Clearing All User Data ===")
        print("⚠️  This will remove ALL users, organizations, and related data!")
        
        confirmation = input("Type 'CLEAR ALL' to confirm: ")
        if confirmation != 'CLEAR ALL':
            print("❌ Operation cancelled")
            return
        
        try:
            # Clear user-related data in dependency order
            print("🗑️  Clearing user role assignments...")
            UserRoleAssignment.query.delete()
            
            print("🗑️  Clearing user statistics...")
            UserStats.query.delete()
            
            print("🗑️  Clearing organization statistics...")
            OrganizationStats.query.delete()
            
            print("🗑️  Clearing billing snapshots...")
            BillingSnapshot.query.delete()
            
            # Clear users (both customer and developer)
            print("🗑️  Clearing all users...")
            user_count = User.query.count()
            User.query.delete()
            
            # Clear organizations
            print("🗑️  Clearing all organizations...")
            org_count = Organization.query.count()
            Organization.query.delete()
            
            # Commit all changes
            db.session.commit()
            
            print("✅ All user data cleared successfully!")
            print(f"   - Removed {user_count} users")
            print(f"   - Removed {org_count} organizations")
            print("   - Removed all role assignments")
            print("   - Removed all statistics")
            print("   - Removed all billing data")
            print("📋 Schema preserved - permissions, roles, and tiers intact")
            print("🔄 Run 'flask init-production' to recreate default data")
            
        except Exception as e:
            print(f"❌ Error clearing user data: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    clear_all_user_data()
