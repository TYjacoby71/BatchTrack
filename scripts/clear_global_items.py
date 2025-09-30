
#!/usr/bin/env python3
"""
Script to clear global items and their associated categories.
This removes the curated global item library and ingredient categories.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.models import db
from app.models.global_item import GlobalItem
from app.models.category import IngredientCategory

def clear_global_items():
    """Clear all global items and their categories"""

    app = create_app()

    with app.app_context():
        try:
            print("🧹 Starting global items cleanup...")

            # Get counts before deletion
            global_items_count = GlobalItem.query.count()
            categories_count = IngredientCategory.query.filter_by(organization_id=None).count()

            print(f"📊 Current state:")
            print(f"   - Global items: {global_items_count}")
            print(f"   - Reference categories: {categories_count}")

            # 1. Clear global items first (they reference categories via FK)
            if global_items_count > 0:
                print(f"🗑️  Clearing {global_items_count} global items...")
                db.session.query(GlobalItem).delete()
                db.session.flush()  # Ensure FK references are cleared

            # 2. Clear reference categories (parent table)
            if categories_count > 0:
                print(f"🗑️  Clearing {categories_count} reference categories...")
                db.session.query(IngredientCategory).filter_by(organization_id=None).delete()

            # Commit all changes
            print("💾 Committing all changes...")
            db.session.commit()
            print("✅ All changes committed successfully!")

            # Verify cleanup
            final_global_items = GlobalItem.query.count()
            final_categories = IngredientCategory.query.filter_by(organization_id=None).count()

            print(f"\n✅ Cleanup complete:")
            print(f"   - Global items remaining: {final_global_items}")
            print(f"   - Reference categories remaining: {final_categories}")

            total_remaining = final_global_items + final_categories

            if total_remaining == 0:
                print("🎉 Perfect! All global items and categories cleared successfully.")
            else:
                print(f"⚠️  Warning: {total_remaining} items still remain unexpectedly.")

        except Exception as e:
            print(f"❌ Error during cleanup: {str(e)}")
            db.session.rollback()
            raise

    return True

if __name__ == '__main__':
    print("⚠️  This will clear ALL global items and reference categories")
    print("✅ Organization-specific categories and inventory will be preserved")
    confirm = input("Type 'CLEAR GLOBAL' to confirm: ")
    if confirm == 'CLEAR GLOBAL':
        clear_global_items()
    else:
        print("❌ Operation cancelled")
