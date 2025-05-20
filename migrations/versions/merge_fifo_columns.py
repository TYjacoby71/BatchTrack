
"""Merge FIFO reference columns

Revision ID: merge_fifo_columns
Revises: update_inventory_tracking
Create Date: 2025-05-20 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_fifo_columns'
down_revision = 'update_inventory_tracking'
branch_labels = None
depends_on = None

def upgrade():
    # Add new column
    op.add_column('inventory_history', sa.Column('fifo_reference_id', sa.Integer(), nullable=True))
    
    # Copy data from old columns
    op.execute("""
        UPDATE inventory_history 
        SET fifo_reference_id = COALESCE(source_fifo_id, credited_to_fifo_id)
        WHERE source_fifo_id IS NOT NULL OR credited_to_fifo_id IS NOT NULL
    """)
    
    # Drop old columns
    op.drop_column('inventory_history', 'source_fifo_id')
    op.drop_column('inventory_history', 'credited_to_fifo_id')

def downgrade():
    # Add old columns back
    op.add_column('inventory_history', sa.Column('source_fifo_id', sa.Integer(), nullable=True))
    op.add_column('inventory_history', sa.Column('credited_to_fifo_id', sa.Integer(), nullable=True))
    
    # Copy data back based on quantity_change sign
    op.execute("""
        UPDATE inventory_history 
        SET source_fifo_id = CASE WHEN quantity_change < 0 THEN fifo_reference_id ELSE NULL END,
            credited_to_fifo_id = CASE WHEN quantity_change > 0 THEN fifo_reference_id ELSE NULL END
        WHERE fifo_reference_id IS NOT NULL
    """)
    
    # Drop new column
    op.drop_column('inventory_history', 'fifo_reference_id')
