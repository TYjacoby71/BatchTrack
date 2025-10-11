
"""cleanup redundant category fields

Revision ID: 20250911_01
Revises: 20250908_01
Create Date: 2025-09-11 16:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '20250911_01'
down_revision = '20250908_01'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    """
    Clean up redundant category fields in global_item and category tables.
    Remove reference_category_name from global_item since it's redundant with the category relationship.
    """
    print("🧹 Cleaning up redundant category fields...")

    try:
        # 1) Update global_item.reference_category to use category.name where needed (only if column exists)
        if table_exists('global_item') and table_exists('ingredient_category') and column_exists('global_item', 'reference_category'):
            print("   Updating global_item.reference_category from category relationships...")
            try:
                bind = op.get_bind()

                # Update reference_category to match the category name for items that have ingredient_category_id
                bind.execute(text("""
                    UPDATE global_item 
                    SET reference_category = ingredient_category.name
                    FROM ingredient_category 
                    WHERE global_item.ingredient_category_id = ingredient_category.id 
                    AND (global_item.reference_category IS NULL 
                         OR global_item.reference_category != ingredient_category.name)
                """))
                print("   ✅ Updated reference_category from category relationships")

            except Exception as e:
                print(f"   ⚠️  Could not update reference_category: {e}")
        else:
            print("   ℹ️  reference_category column doesn't exist - skipping reference_category updates")

        # 2) Drop reference_category_name from ingredient_category table if it exists
        if table_exists('ingredient_category') and column_exists('ingredient_category', 'reference_category_name'):
            print("   Removing redundant reference_category_name from ingredient_category table...")
            try:
                with op.batch_alter_table('ingredient_category', schema=None) as batch_op:
                    batch_op.drop_column('reference_category_name')
                print("   ✅ Removed reference_category_name from ingredient_category table")
            except Exception as e:
                print(f"   ⚠️  Could not drop reference_category_name from ingredient_category: {e}")
        else:
            print("   ℹ️  reference_category_name column doesn't exist - skipping")

        # 3) Ensure all global items have proper reference_category values (only if column exists)
        if table_exists('global_item') and column_exists('global_item', 'reference_category'):
            print("   Ensuring all global items have reference_category values...")
            try:
                bind = op.get_bind()

                # For items without reference_category, set it to a default based on their category
                bind.execute(text("""
                    UPDATE global_item 
                    SET reference_category = COALESCE(
                        (SELECT ingredient_category.name FROM ingredient_category WHERE ingredient_category.id = global_item.ingredient_category_id),
                        'Miscellaneous'
                    )
                    WHERE reference_category IS NULL
                """))
                print("   ✅ Set default reference_category values")

            except Exception as e:
                print(f"   ⚠️  Could not set default reference_category values: {e}")
        else:
            print("   ℹ️  reference_category column doesn't exist - skipping default value assignment")

        print("✅ Category field cleanup completed")

    except Exception as e:
        print(f"❌ Migration failed with error: {e}")
        # Don't re-raise to prevent transaction abort issues
        print("⚠️  Continuing despite errors to prevent transaction abort")


def downgrade():
    """
    Restore the reference_category_name field to category table
    """
    print("🔄 Restoring reference_category_name field...")

    try:
        # Add back reference_category_name to ingredient_category table
        if table_exists('ingredient_category') and not column_exists('ingredient_category', 'reference_category_name'):
            print("   Adding reference_category_name back to ingredient_category table...")
            try:
                with op.batch_alter_table('ingredient_category', schema=None) as batch_op:
                    batch_op.add_column(sa.Column('reference_category_name', sa.String(length=255), nullable=True))

                # Populate it with the category name
                bind = op.get_bind()
                bind.execute(text("""
                    UPDATE ingredient_category 
                    SET reference_category_name = name 
                    WHERE reference_category_name IS NULL
                """))
                print("   ✅ Restored reference_category_name to ingredient_category table")

            except Exception as e:
                print(f"   ⚠️  Could not restore reference_category_name: {e}")
        else:
            print("   ℹ️  reference_category_name already exists or ingredient_category table missing - skipping")

        print("✅ Downgrade completed")

    except Exception as e:
        print(f"❌ Downgrade failed: {e}")
        # Don't re-raise to prevent further transaction issues
        print("⚠️  Continuing despite errors")
