
"""Add remaining quantity tracking to InventoryHistory

Revision ID: update_inventory_tracking
Revises: dbindex
Create Date: 2025-05-19 22:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'update_inventory_tracking'
down_revision = 'dbindex'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('inventory_history', sa.Column('remaining_quantity', sa.Float(), nullable=True))
    op.add_column('inventory_history', sa.Column('is_perishable', sa.Boolean(), default=False))
    op.add_column('inventory_history', sa.Column('expiration_date', sa.DateTime(), nullable=True))
    op.add_column('inventory_history', sa.Column('shelf_life_days', sa.Integer(), nullable=True))

def downgrade():
    op.drop_column('inventory_history', 'remaining_quantity')
    op.drop_column('inventory_history', 'is_perishable') 
    op.drop_column('inventory_history', 'expiration_date')
    op.drop_column('inventory_history', 'shelf_life_days')
