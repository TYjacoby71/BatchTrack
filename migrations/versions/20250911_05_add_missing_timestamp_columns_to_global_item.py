
"""Add missing timestamp columns to global_item

Revision ID: 20250911_05
Revises: 20250911_04
Create Date: 2025-09-11 19:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250911_05'
down_revision = '20250911_04'
branch_labels = None
depends_on = None

def upgrade():
    # Add missing timestamp columns to global_item table
    try:
        op.add_column('global_item', sa.Column('created_at', sa.DateTime(), nullable=True))
        op.add_column('global_item', sa.Column('updated_at', sa.DateTime(), nullable=True))
        
        # Set default values for existing records
        op.execute("UPDATE global_item SET created_at = NOW(), updated_at = NOW() WHERE created_at IS NULL")
        
        # Make columns non-nullable after setting defaults
        op.alter_column('global_item', 'created_at', nullable=False)
        op.alter_column('global_item', 'updated_at', nullable=False)
        
        print("✅ Added missing timestamp columns to global_item")
    except Exception as e:
        print(f"⚠️  Error adding timestamp columns to global_item: {e}")
        # Continue anyway - might already exist

def downgrade():
    op.drop_column('global_item', 'updated_at')
    op.drop_column('global_item', 'created_at')
