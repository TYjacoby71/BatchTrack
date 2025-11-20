#!/usr/bin/env python3
"""
Script to clear all user data while preserving schema and global items.
This removes all organization-scoped data for testing purposes.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.models import db
from app.models.models import (
    User, Organization
)
from app.models.inventory import InventoryItem
from app.models.batch import Batch
from app.models.recipe import Recipe
from app.models.product import Product, ProductVariant, ProductSKU
from app.models.unified_inventory_history import UnifiedInventoryHistory
from app.models.inventory_lot import InventoryLot
from app.models.user_role_assignment import UserRoleAssignment
from app.models.statistics import UserStats, OrganizationStats
from app.models.user_preferences import UserPreferences
from app.models.reservation import Reservation

def clear_all_data():
    """Clear all user data while preserving schema"""

    app = create_app()

    with app.app_context():
        try:
            print("🧹 Starting complete data cleanup...")

            # Get counts before deletion
            user_count = User.query.filter_by(user_type='customer').count()
            org_count = Organization.query.count()
            inventory_count = InventoryItem.query.count()
            batch_count = Batch.query.count()
            recipe_count = Recipe.query.count()
            product_count = Product.query.count()
            history_count = UnifiedInventoryHistory.query.count()
            lot_count = InventoryLot.query.count()

            print(f"📊 Current state:")
            print(f"   - Customer users: {user_count}")
            print(f"   - Organizations: {org_count}")
            print(f"   - Inventory items: {inventory_count}")
            print(f"   - Batches: {batch_count}")
            print(f"   - Recipes: {recipe_count}")
            print(f"   - Products: {product_count}")
            print(f"   - History entries: {history_count}")
            print(f"   - FIFO lots: {lot_count}")

            # Clear in proper dependency order to avoid foreign key violations
            # CRITICAL: Clear child tables before parent tables

            # 1. Clear inventory history first (references many other tables)
            if history_count > 0:
                print(f"🗑️  Clearing {history_count} inventory history entries...")
                db.session.query(UnifiedInventoryHistory).delete()

            # 2. Clear FIFO lots
            if lot_count > 0:
                print(f"🗑️  Clearing {lot_count} FIFO lots...")
                db.session.query(InventoryLot).delete()

            # 3. Clear reservations
            reservation_count = Reservation.query.count()
            if reservation_count > 0:
                print(f"🗑️  Clearing {reservation_count} reservations...")
                db.session.query(Reservation).delete()

            # 4. Clear product-related data (in dependency order)
            if product_count > 0:
                print(f"🗑️  Clearing product data...")
                db.session.query(ProductSKU).delete()
                db.session.query(ProductVariant).delete()
                db.session.query(Product).delete()

            # 5. Clear batch-related data (child tables first!)
            if batch_count > 0:
                print(f"🗑️  Clearing batch ingredients...")
                from app.models.batch import BatchIngredient
                db.session.query(BatchIngredient).delete()

                print(f"🗑️  Clearing batch consumables...")
                from app.models.batch import BatchConsumable
                db.session.query(BatchConsumable).delete()

                print(f"🗑️  Clearing batch containers...")
                from app.models.batch import BatchContainer
                db.session.query(BatchContainer).delete()

                print(f"🗑️  Clearing extra batch containers...")
                from app.models.batch import ExtraBatchContainer
                db.session.query(ExtraBatchContainer).delete()

                print(f"🗑️  Clearing batch timers...")
                from app.models.batch import BatchTimer
                db.session.query(BatchTimer).delete()

                print(f"🗑️  Clearing extra batch ingredients...")
                from app.models.batch import ExtraBatchIngredient
                db.session.query(ExtraBatchIngredient).delete()

                print(f"🗑️  Clearing extra batch consumables...")
                from app.models.batch import ExtraBatchConsumable
                db.session.query(ExtraBatchConsumable).delete()

                print(f"🗑️  Clearing {batch_count} batches...")
                db.session.query(Batch).delete()

            # 6. Clear recipe-related data (child tables first!)
            if recipe_count > 0:
                print(f"🗑️  Clearing recipe ingredients...")
                from app.models.recipe import RecipeIngredient
                db.session.query(RecipeIngredient).delete()

                print(f"🗑️  Clearing recipe consumables...")
                from app.models.recipe import RecipeConsumable
                db.session.query(RecipeConsumable).delete()

                print(f"🗑️  Clearing {recipe_count} recipes...")
                db.session.query(Recipe).delete()

            # 7. Clear inventory items
            if inventory_count > 0:
                print(f"🗑️  Clearing {inventory_count} inventory items...")
                db.session.query(InventoryItem).delete()

            # 8. Clear user-related data
            if user_count > 0:
                customer_user_ids = [u.id for u in User.query.filter_by(user_type='customer').all()]

                if customer_user_ids:
                    print(f"🗑️  Clearing user preferences and role assignments...")
                    db.session.query(UserPreferences).filter(
                        UserPreferences.user_id.in_(customer_user_ids)
                    ).delete(synchronize_session=False)

                    db.session.query(UserRoleAssignment).filter(
                        UserRoleAssignment.user_id.in_(customer_user_ids)
                    ).delete(synchronize_session=False)

                    # Clear conversion logs that reference these users
                    print(f"🗑️  Clearing conversion logs...")
                    from app.models.unit import ConversionLog
                    db.session.query(ConversionLog).filter(
                        ConversionLog.user_id.in_(customer_user_ids)
                    ).delete(synchronize_session=False)

                print(f"🗑️  Clearing {user_count} customer users...")
                db.session.query(User).filter_by(user_type='customer').delete()

            # 9. Clear organization data
            if org_count > 0:
                org_ids = [o.id for o in Organization.query.all()]

                if org_ids:
                    print(f"🗑️  Clearing organization statistics...")
                    db.session.query(OrganizationStats).delete()

                    # Clear ingredient categories before organizations (foreign key dependency)
                    print(f"🗑️  Clearing ingredient categories...")
                    from app.models.category import IngredientCategory
                    db.session.query(IngredientCategory).delete()

                    print(f"🗑️  Clearing {org_count} organizations...")
                    db.session.query(Organization).delete()

            # 10. Clear remaining user stats
            user_stats_count = UserStats.query.count()
            if user_stats_count > 0:
                print(f"🗑️  Clearing {user_stats_count} user statistics...")
                db.session.query(UserStats).delete()

            # Commit all changes
            print("💾 Committing all changes...")
            db.session.commit()
            print("✅ All changes committed successfully!")

            # Verify cleanup
            final_users = User.query.filter_by(user_type='customer').count()
            final_orgs = Organization.query.count()
            final_inventory = InventoryItem.query.count()
            final_batches = Batch.query.count()
            final_recipes = Recipe.query.count()
            final_products = Product.query.count()
            final_history = UnifiedInventoryHistory.query.count()
            final_lots = InventoryLot.query.count()

            print(f"\n✅ Cleanup complete:")
            print(f"   - Customer users remaining: {final_users}")
            print(f"   - Organizations remaining: {final_orgs}")
            print(f"   - Inventory items remaining: {final_inventory}")
            print(f"   - Batches remaining: {final_batches}")
            print(f"   - Recipes remaining: {final_recipes}")
            print(f"   - Products remaining: {final_products}")
            print(f"   - History entries remaining: {final_history}")
            print(f"   - FIFO lots remaining: {final_lots}")

            total_remaining = (final_users + final_orgs + final_inventory + 
                             final_batches + final_recipes + final_products + 
                             final_history + final_lots)

            if total_remaining == 0:
                print("🎉 Perfect! All user data cleared successfully.")
                print("   Global items, permissions, and schema preserved.")
            else:
                print("⚠️  Some data may not have been cleared completely.")

        except Exception as e:
            print(f"❌ Error during cleanup: {str(e)}")
            db.session.rollback()
            raise

    return True

if __name__ == '__main__':
    print("⚠️  This will clear ALL user data (users, orgs, inventory, batches, etc.)")
    print("✅ Global items, permissions, and schema will be preserved")
    confirm = input("Type 'CLEAR ALL DATA' to confirm: ")
    if confirm == 'CLEAR ALL DATA':
        clear_all_data()
    else:
        print("❌ Operation cancelled")