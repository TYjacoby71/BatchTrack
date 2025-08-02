
#!/usr/bin/env python3
"""
Clear Customer Users Only - PostgreSQL Safe
Removes all customer users and their related data while preserving developer users and schema.
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

def clear_customer_users_only():
    """Clear all customer users and organizations while preserving developers and schema"""
    
    print("⚠️  This removes all CUSTOMER users and organizations")
    print("✅ Developer users will be preserved")
    print("✅ Schema (permissions, roles, tiers) will be preserved")
    
    confirmation = input("Type 'CLEAR CUSTOMER USERS' to confirm: ")
    if confirmation != 'CLEAR CUSTOMER USERS':
        print("❌ Operation cancelled")
        return

    app = create_app()
    
    with app.app_context():
        try:
            # Step 1: Clear user preferences (foreign key to user)
            print("🗑️  Clearing user preferences...")
            customer_user_ids = [u.id for u in User.query.filter_by(user_type='customer').all()]
            if customer_user_ids:
                db.session.execute(db.text("DELETE FROM user_preferences WHERE user_id = ANY(:user_ids)"), {"user_ids": customer_user_ids})
            
            # Step 2: Clear user role assignments for customer users
            print("🗑️  Clearing customer user role assignments...")
            if customer_user_ids:
                db.session.execute(db.text("DELETE FROM user_role_assignment WHERE user_id = ANY(:user_ids)"), {"user_ids": customer_user_ids})
            
            # Step 3: Clear user statistics
            print("🗑️  Clearing user statistics...")
            if customer_user_ids:
                db.session.execute(db.text("DELETE FROM user_stats WHERE user_id = ANY(:user_ids)"), {"user_ids": customer_user_ids})
            
            # Step 4: Clear organization statistics
            print("🗑️  Clearing organization statistics...")
            org_ids = [o.id for o in Organization.query.all()]
            if org_ids:
                db.session.execute(db.text("DELETE FROM organization_stats WHERE organization_id = ANY(:org_ids)"), {"org_ids": org_ids})
            
            # Step 5: Clear billing snapshots
            print("🗑️  Clearing billing snapshots...")
            if org_ids:
                db.session.execute(db.text("DELETE FROM billing_snapshots WHERE organization_id = ANY(:org_ids)"), {"org_ids": org_ids})
            
            # Step 6: Clear any other tables that reference users (need to check what exists)
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
                        if customer_user_ids:
                            # Set references to NULL instead of deleting records (preserve data)
                            db.session.execute(db.text(f"UPDATE {table} SET {col_name} = NULL WHERE {col_name} = ANY(:user_ids)"), {"user_ids": customer_user_ids})
            
            # Step 7: Clear all customer users
            print("🗑️  Clearing customer users...")
            db.session.execute(db.text("DELETE FROM \"user\" WHERE user_type = 'customer'"))
            
            # Step 8: Clear all organizations
            print("🗑️  Clearing organizations...")
            db.session.execute(db.text("DELETE FROM organization"))
            
            # Commit all changes
            db.session.commit()
            print("✅ Customer users and organizations cleared successfully")
            
            # Summary
            remaining_users = User.query.count()
            remaining_orgs = Organization.query.count()
            print(f"\n📊 Summary:")
            print(f"Remaining users: {remaining_users} (should be developers only)")
            print(f"Remaining organizations: {remaining_orgs} (should be 0)")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error clearing customer user data: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            return False
    
    return True

if __name__ == "__main__":
    clear_customer_users_only()
