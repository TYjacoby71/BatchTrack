
"""Add reference guide integration fields

Revision ID: add_reference_guide_integration
Revises: add_container_capacity_columns
Create Date: 2025-09-04 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_reference_guide_integration'
down_revision = 'add_capacity_fields'
branch_labels = None
depends_on = None

def upgrade():
    """Add reference guide integration fields"""
    
    # Add fields to inventory_item table
    op.add_column('inventory_item', sa.Column('reference_item_name', sa.String(128), nullable=True))
    op.add_column('inventory_item', sa.Column('density_source', sa.String(32), nullable=True, default='manual'))
    
    # Add fields to ingredient_category table
    op.add_column('ingredient_category', sa.Column('reference_category_name', sa.String(64), nullable=True))
    op.add_column('ingredient_category', sa.Column('is_reference_category', sa.Boolean(), nullable=True, default=False))
    
    print("✅ Added reference guide integration fields")

def downgrade():
    """Remove reference guide integration fields"""
    
    # Remove fields from inventory_item table
    op.drop_column('inventory_item', 'density_source')
    op.drop_column('inventory_item', 'reference_item_name')
    
    # Remove fields from ingredient_category table
    op.drop_column('ingredient_category', 'is_reference_category')
    op.drop_column('ingredient_category', 'reference_category_name')
    
    print("✅ Removed reference guide integration fields")
