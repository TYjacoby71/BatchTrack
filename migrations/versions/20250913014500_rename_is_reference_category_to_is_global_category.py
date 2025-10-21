
"""rename is_reference_category to is_global_category

Revision ID: 20250913014500
Revises: 20250911_06
Create Date: 2025-09-13 01:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect


# revision identifiers, used by Alembic.
revision = '20250913014500'
down_revision = '20250911_06'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Portable table existence check (works on SQLite and Postgres)."""
    try:
        bind = op.get_bind()
        return table_name in inspect(bind).get_table_names()
    except Exception:
        return False


def column_exists(table_name: str, column_name: str) -> bool:
    """Portable column existence check."""
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        cols = [c['name'] for c in inspector.get_columns(table_name)]
        return column_name in cols
    except Exception:
        return False


def upgrade():
    """Rename is_reference_category to is_global_category for clarity"""
    print("🔄 Renaming is_reference_category to is_global_category...")

    if table_exists('ingredient_category'):
        # Add the new column
        if not column_exists('ingredient_category', 'is_global_category'):
            print("   Adding is_global_category column...")
            op.add_column('ingredient_category', sa.Column('is_global_category', sa.Boolean, default=False))

        bind = op.get_bind()
        dialect = getattr(bind.dialect, 'name', '')

        # Copy data from old column to new column if present
        if column_exists('ingredient_category', 'is_reference_category'):
            print("   Copying data from is_reference_category to is_global_category...")
            bind.execute(text("""
                UPDATE ingredient_category 
                SET is_global_category = is_reference_category 
                WHERE is_reference_category IS NOT NULL
            """))

            # Drop the old column
            print("   Dropping is_reference_category column...")
            try:
                op.drop_column('ingredient_category', 'is_reference_category')
            except Exception:
                # SQLite may not support drop column without batch; ignore
                pass
        else:
            # Set default values for global categories
            print("   Setting default values for global categories...")
            if column_exists('ingredient_category', 'is_active'):
                true_literal = '1' if dialect == 'sqlite' else 'true'
                bind.execute(text(f"""
                    UPDATE ingredient_category 
                    SET is_global_category = {true_literal}
                    WHERE organization_id IS NULL AND is_active = {true_literal}
                """))
            else:
                # Fallback: mark organization-scoped NULL as global
                bind.execute(text("""
                    UPDATE ingredient_category 
                    SET is_global_category = TRUE
                    WHERE organization_id IS NULL
                """))

    print("✅ Successfully renamed field to is_global_category")


def downgrade():
    """Revert is_global_category back to is_reference_category"""
    print("🔄 Reverting is_global_category to is_reference_category...")

    if table_exists('ingredient_category'):
        # Add the old column back
        if not column_exists('ingredient_category', 'is_reference_category'):
            print("   Adding is_reference_category column...")
            op.add_column('ingredient_category', sa.Column('is_reference_category', sa.Boolean, default=False))

        # Copy data back
        if column_exists('ingredient_category', 'is_global_category'):
            print("   Copying data from is_global_category to is_reference_category...")
            bind = op.get_bind()
            bind.execute(text("""
                UPDATE ingredient_category 
                SET is_reference_category = is_global_category 
                WHERE is_global_category IS NOT NULL
            """))

            # Drop the new column
            print("   Dropping is_global_category column...")
            try:
                op.drop_column('ingredient_category', 'is_global_category')
            except Exception as e:
                print(f"   ⚠️  Could not drop is_global_category column: {e}")

    print("✅ Successfully reverted to is_reference_category")
