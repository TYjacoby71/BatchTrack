
"""Add missing fields to InventoryItem

Revision ID: add_missing_inventory_fields
Revises: 2fbddb7c10ea
Create Date: 2025-06-24 22:55:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_missing_inventory_fields'
down_revision = '2fbddb7c10ea'
branch_labels = None
depends_on = None

def upgrade():
    # Add missing columns to inventory_item table
    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_archived', sa.Boolean(), nullable=True, default=False))
        batch_op.add_column(sa.Column('is_perishable', sa.Boolean(), nullable=True, default=False))
        batch_op.add_column(sa.Column('shelf_life_days', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('expiration_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('storage_amount', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('storage_unit', sa.String(length=32), nullable=True))

def downgrade():
    # Remove the added columns
    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        batch_op.drop_column('storage_unit')
        batch_op.drop_column('storage_amount')
        batch_op.drop_column('expiration_date')
        batch_op.drop_column('shelf_life_days')
        batch_op.drop_column('is_perishable')
        batch_op.drop_column('is_archived')
