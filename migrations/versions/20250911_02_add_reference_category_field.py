
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
    # Add reference_category field to global_item table
    try:
        op.add_column('global_item', sa.Column('reference_category', sa.String(64), nullable=True))
        op.create_index('ix_global_item_reference_category', 'global_item', ['reference_category'])
        print("✅ Added reference_category field to global_item table")
    except Exception as e:
        print(f"Migration failed: {e}")
        # Column might already exist, continue

def downgrade():
    try:
        op.drop_index('ix_global_item_reference_category', 'global_item')
        op.drop_column('global_item', 'reference_category')
    except Exception:
        pass
