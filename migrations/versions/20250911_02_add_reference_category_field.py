
"""Add reference_category field to global_item table

Revision ID: 20250911_02
Revises: 20250911_01
Create Date: 2025-09-11 18:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250911_02'
down_revision = '20250911_01'
branch_labels = None
depends_on = None

def upgrade():
    # Add reference_category field to global_item table if it doesn't exist
    from sqlalchemy import inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('global_item')]
    
    if 'reference_category' not in columns:
        op.add_column('global_item', sa.Column('reference_category', sa.String(64), nullable=True))
        print("✅ Added reference_category field to global_item table")
    else:
        print("⚠️ reference_category column already exists, skipping")
    
    # Check if index exists before creating
    indexes = [idx['name'] for idx in inspector.get_indexes('global_item')]
    if 'ix_global_item_reference_category' not in indexes:
        try:
            op.create_index('ix_global_item_reference_category', 'global_item', ['reference_category'])
            print("✅ Created index on reference_category")
        except Exception as e:
            print(f"⚠️ Index creation failed (might already exist): {e}")

def downgrade():
    # Drop index and column if they exist
    from sqlalchemy import inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Drop index if it exists
    indexes = [idx['name'] for idx in inspector.get_indexes('global_item')]
    if 'ix_global_item_reference_category' in indexes:
        try:
            op.drop_index('ix_global_item_reference_category', 'global_item')
            print("✅ Dropped index on reference_category")
        except Exception as e:
            print(f"⚠️ Failed to drop index: {e}")
    
    # Drop column if it exists
    columns = [col['name'] for col in inspector.get_columns('global_item')]
    if 'reference_category' in columns:
        try:
            op.drop_column('global_item', 'reference_category')
            print("✅ Dropped reference_category column")
        except Exception as e:
            print(f"⚠️ Failed to drop column: {e}")
