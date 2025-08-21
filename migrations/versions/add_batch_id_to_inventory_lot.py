
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
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('inventory_lot', schema=None) as batch_op:
        # Add batch_id column
        batch_op.add_column(sa.Column('batch_id', sa.Integer(), nullable=True))
        
        # Add foreign key constraint
        batch_op.create_foreign_key(
            'fk_inventory_lot_batch_id', 
            'batch', 
            ['batch_id'], 
            ['id']
        )
        
        # Add index for performance
        batch_op.create_index('idx_inventory_lot_batch', ['batch_id'])

def downgrade():
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('inventory_lot', schema=None) as batch_op:
        # Remove index
        batch_op.drop_index('idx_inventory_lot_batch')
        
        # Remove foreign key constraint
        batch_op.drop_constraint('fk_inventory_lot_batch_id', type_='foreignkey')
        
        # Remove column
        batch_op.drop_column('batch_id')
