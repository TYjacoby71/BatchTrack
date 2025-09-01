
"""Add capacity fields to inventory items and migrate container data

Revision ID: add_capacity_fields
Revises: add_comprehensive_stats
Create Date: 2025-09-01 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_capacity_fields'
down_revision = 'add_comprehensive_stats'
branch_labels = None
depends_on = None


def upgrade():
    # Add new capacity columns
    op.add_column('inventory_item', sa.Column('capacity', sa.Float(), nullable=True))
    op.add_column('inventory_item', sa.Column('capacity_unit', sa.String(32), nullable=True))
    
    # Migrate existing container data
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE inventory_item 
        SET capacity = capacity, 
            capacity_unit = capacity_unit 
        WHERE type = 'container' 
        AND capacity IS NOT NULL
    """))
    
    # Drop the legacy columns
    op.drop_column('inventory_item', 'capacity')
    op.drop_column('inventory_item', 'capacity_unit')


def downgrade():
    # Re-add legacy columns
    op.add_column('inventory_item', sa.Column('capacity', sa.Float(), nullable=True))
    op.add_column('inventory_item', sa.Column('capacity_unit', sa.String(32), nullable=True))
    
    # Migrate data back
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE inventory_item 
        SET capacity = capacity, 
            capacity_unit = capacity_unit 
        WHERE type = 'container' 
        AND capacity IS NOT NULL
    """))
    
    # Drop new columns
    op.drop_column('inventory_item', 'capacity_unit')
    op.drop_column('inventory_item', 'capacity')
