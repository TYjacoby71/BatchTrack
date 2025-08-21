
"""Create inventory_lot table for proper FIFO tracking

Revision ID: create_inventory_lot
Revises: 6f9bc65166b3
Create Date: 2025-08-21 04:57:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'create_inventory_lot'
down_revision = '6f9bc65166b3'
branch_labels = None
depends_on = None


def upgrade():
    # Create inventory_lot table
    op.create_table(
        'inventory_lot',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('remaining_quantity', sa.Float(), nullable=False, default=0.0),
        sa.Column('original_quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(32), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=False, default=0.0),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('received_date', sa.DateTime(), nullable=False),
        sa.Column('expiration_date', sa.DateTime(), nullable=True),
        sa.Column('shelf_life_days', sa.Integer(), nullable=True),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('fifo_code', sa.String(32), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.UniqueConstraint('fifo_code'),
        sa.CheckConstraint('remaining_quantity >= 0', name='check_remaining_quantity_non_negative'),
        sa.CheckConstraint('original_quantity > 0', name='check_original_quantity_positive'),
        sa.CheckConstraint('remaining_quantity <= original_quantity', name='check_remaining_not_exceeds_original'),
    )

    # Create indexes for performance
    op.create_index('idx_inventory_lot_item_remaining', 'inventory_lot', ['inventory_item_id', 'remaining_quantity'])
    op.create_index('idx_inventory_lot_received_date', 'inventory_lot', ['received_date'])
    op.create_index('idx_inventory_lot_expiration', 'inventory_lot', ['expiration_date'])
    op.create_index('idx_inventory_lot_organization', 'inventory_lot', ['organization_id'])


def downgrade():
    # Drop indexes first
    op.drop_index('idx_inventory_lot_organization')
    op.drop_index('idx_inventory_lot_expiration')
    op.drop_index('idx_inventory_lot_received_date')
    op.drop_index('idx_inventory_lot_item_remaining')
    
    # Drop table
    op.drop_table('inventory_lot')
