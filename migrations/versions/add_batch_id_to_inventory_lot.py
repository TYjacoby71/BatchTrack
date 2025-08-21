
"""Add batch_id to inventory_lot table

Revision ID: add_batch_id_to_inventory_lot
Revises: add_affected_lot_id_simple
Create Date: 2025-08-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_batch_id_to_inventory_lot'
down_revision = 'add_affected_lot_id_simple'
branch_labels = None
depends_on = None

def upgrade():
    # Add batch_id column to inventory_lot table
    op.add_column('inventory_lot', sa.Column('batch_id', sa.Integer(), nullable=True))
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_inventory_lot_batch_id', 
        'inventory_lot', 
        'batch', 
        ['batch_id'], 
        ['id']
    )
    
    # Add index for performance
    op.create_index('idx_inventory_lot_batch', 'inventory_lot', ['batch_id'])

def downgrade():
    # Remove index
    op.drop_index('idx_inventory_lot_batch', table_name='inventory_lot')
    
    # Remove foreign key constraint
    op.drop_constraint('fk_inventory_lot_batch_id', 'inventory_lot', type_='foreignkey')
    
    # Remove column
    op.drop_column('inventory_lot', 'batch_id')
