
"""Add batch inventory tracking

Revision ID: add_batch_inventory
Revises: 2af2ecb1908a
Create Date: 2024-01-15 10:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_batch_inventory'
down_revision = '2af2ecb1908a' 
branch_labels = ('remainingquantity',)
depends_on = None

def upgrade():
    # Add remaining_quantity to batch table
    op.add_column('batch', sa.Column('remaining_quantity', sa.Float(), nullable=True))
    
    # Create batch_inventory_log table
    op.create_table('batch_inventory_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('quantity_change', sa.Float(), nullable=False),
        sa.Column('reason', sa.String(32), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('batch_inventory_log')
    op.drop_column('batch', 'remaining_quantity')
