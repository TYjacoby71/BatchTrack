
"""Add missing timestamp columns to global_item

Revision ID: 20250911_05
Revises: 20250911_04
Create Date: 2025-09-11

"""
from alembic import op
import sqlalchemy as sa

# Helper functions to check for table and column existence
def table_exists(table_name):
    from sqlalchemy.engine import reflection
    inspector = reflection.Inspector(op.get_context().bind)
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    from sqlalchemy.engine import reflection
    inspector = reflection.Inspector(op.get_context().bind)
    columns = inspector.get_columns(table_name)
    return any(c['name'] == column_name for c in columns)

# revision identifiers, used by Alembic.
revision = '20250911_05'
down_revision = '20250911_04'
branch_labels = None
depends_on = None


def upgrade():
    """Add missing timestamp columns to global_item if they don't exist"""
    
    if not table_exists('global_item'):
        print("⚠️ global_item table does not exist - skipping")
        return
    
    # Check and add created_at column
    if not column_exists('global_item', 'created_at'):
        try:
            print("   Adding created_at column to global_item...")
            op.add_column('global_item', sa.Column('created_at', sa.DateTime(), nullable=True))
            print("✅ Added created_at column to global_item")
        except Exception as e:
            print(f"⚠️ Error adding created_at to global_item: {e}")
    else:
        print("✅ created_at column already exists in global_item - skipping")
    
    # Check and add updated_at column
    if not column_exists('global_item', 'updated_at'):
        try:
            print("   Adding updated_at column to global_item...")
            op.add_column('global_item', sa.Column('updated_at', sa.DateTime(), nullable=True))
            print("✅ Added updated_at column to global_item")
        except Exception as e:
            print(f"⚠️ Error adding updated_at to global_item: {e}")
    else:
        print("✅ updated_at column already exists in global_item - skipping")


def downgrade():
    """Remove timestamp columns from global_item"""
    if not table_exists('global_item'):
        print("⚠️ global_item table does not exist - skipping downgrade")
        return
    
    if column_exists('global_item', 'updated_at'):
        try:
            op.drop_column('global_item', 'updated_at')
            print("Removed updated_at column from global_item")
        except Exception as e:
            print(f"⚠️ Error removing updated_at from global_item: {e}")
    
    if column_exists('global_item', 'created_at'):
        try:
            op.drop_column('global_item', 'created_at')
            print("Removed created_at column from global_item")
        except Exception as e:
            print(f"⚠️ Error removing created_at from global_item: {e}")
