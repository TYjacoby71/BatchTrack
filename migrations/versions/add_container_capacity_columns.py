
"""Add container capacity columns

Revision ID: add_container_capacity
Revises: add_comprehensive_stats
Create Date: 2025-09-02 18:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_container_capacity'
down_revision = 'add_comprehensive_stats'
branch_labels = None
depends_on = None

def upgrade():
    """Add capacity and capacity_unit columns to inventory_item table for containers"""
    
    # Add capacity column (renamed from storage_amount)
    op.add_column('inventory_item', sa.Column('capacity', sa.Float(), nullable=True))
    
    # Add capacity_unit column (renamed from storage_unit)  
    op.add_column('inventory_item', sa.Column('capacity_unit', sa.String(32), nullable=True))
    
    print("✅ Added capacity and capacity_unit columns to inventory_item table")

def downgrade():
    """Remove capacity columns"""
    op.drop_column('inventory_item', 'capacity_unit')
    op.drop_column('inventory_item', 'capacity')
    print("✅ Removed capacity columns from inventory_item table")
