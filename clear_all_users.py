
#!/usr/bin/env python3
"""
Clear All Users - PostgreSQL Safe
Removes all users, organizations, and related data while preserving schema.
Handles foreign key constraints in proper dependency order.
"""

import sys
from app import create_app
from app.extensions import db
from app.models.models import User, Organization
from app.models.user_role_assignment import UserRoleAssignment
from app.models.statistics import UserStats, OrganizationStats
from app.models.billing_snapshot import BillingSnapshot
from app.models.user_preferences import UserPreferences

def clear_all_user_data():
    """Clear all user-related data while preserving schema"""
    
    print("⚠️  This removes ALL users, organizations, and related data")
    print("✅ Schema (permissions, roles, tiers) will be preserved")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Show what will be deleted
            user_count = User.query.count()
            org_count = Organization.query.count()
            dev_count = User.query.filter_by(user_type='developer').count()
            customer_count = User.query.filter_by(user_type='customer').count()
            
            print(f"📊 Current state:")
            print(f"   - Total users: {user_count}")
            print(f"   - Developer users: {dev_count}")
            print(f"   - Customer users: {customer_count}")
            print(f"   - Organizations: {org_count}")
            
            confirmation = input("Type 'CLEAR ALL' to confirm: ")
            if confirmation != 'CLEAR ALL':
                print("❌ Operation cancelled")
                return False
            
            # Get all user IDs for efficient bulk operations
            all_user_ids = [u.id for u in User.query.all()]
            all_org_ids = [o.id for o in Organization.query.all()]
            
            # Step 1: Clear user preferences (foreign key to user)
            print("🗑️  Clearing user preferences...")
            if all_user_ids:
                db.session.execute(db.text("DELETE FROM user_preferences WHERE user_id = ANY(:user_ids)"), {"user_ids": all_user_ids})
            
            # Step 2: Clear user role assignments
            print("🗑️  Clearing user role assignments...")
            if all_user_ids:
                db.session.execute(db.text("DELETE FROM user_role_assignment WHERE user_id = ANY(:user_ids)"), {"user_ids": all_user_ids})
            
            # Step 3: Clear user statistics
            print("🗑️  Clearing user statistics...")
            if all_user_ids:
                db.session.execute(db.text("DELETE FROM user_stats WHERE user_id = ANY(:user_ids)"), {"user_ids": all_user_ids})
            
            # Step 4: Clear organization statistics
            print("🗑️  Clearing organization statistics...")
            if all_org_ids:
                db.session.execute(db.text("DELETE FROM organization_stats WHERE organization_id = ANY(:org_ids)"), {"org_ids": all_org_ids})
            
            # Step 5: Clear billing snapshots
            print("🗑️  Clearing billing snapshots...")
            if all_org_ids:
                db.session.execute(db.text("DELETE FROM billing_snapshots WHERE organization_id = ANY(:org_ids)"), {"org_ids": all_org_ids})
            
            # Step 6: Clear any other tables that reference users
            print("🗑️  Clearing other user-related data...")
            
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
                    print(f"   Clearing {table} user references...")
                    for column in result:
                        col_name = column[0]
                        if all_user_ids:
                            # Set references to NULL instead of deleting records (preserve data)
                            db.session.execute(db.text(f"UPDATE {table} SET {col_name} = NULL WHERE {col_name} = ANY(:user_ids)"), {"user_ids": all_user_ids})
            
            # Step 7: Clear all users
            print("🗑️  Clearing all users...")
            db.session.execute(db.text("DELETE FROM \"user\""))
            
            # Step 8: Clear all organizations
            print("🗑️  Clearing all organizations...")
            db.session.execute(db.text("DELETE FROM organization"))
            
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
            
            # Final verification
            remaining_users = User.query.count()
            remaining_orgs = Organization.query.count()
            print(f"\n📊 Final state:")
            print(f"Remaining users: {remaining_users} (should be 0)")
            print(f"Remaining organizations: {remaining_orgs} (should be 0)")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error clearing user data: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            return False
    
    return True

if __name__ == '__main__':
    clear_all_user_data()
