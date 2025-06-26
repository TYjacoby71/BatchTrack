
"""Add POS integration fields

Revision ID: pos_integration_001
Revises: e04a3508f9f7
Create Date: 2025-06-26 18:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'pos_integration_001'
down_revision = 'e04a3508f9f7'
branch_labels = None
depends_on = None

def upgrade():
    # Add POS integration fields to inventory_item
    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('frozen_quantity', sa.Float(), default=0.0))
        batch_op.add_column(sa.Column('available_quantity', sa.Float(), default=0.0))
    
    # Add POS integration fields to inventory_history
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('order_id', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('reservation_id', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('is_reserved', sa.Boolean(), default=False))

def downgrade():
    # Remove POS integration fields from inventory_history
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        batch_op.drop_column('is_reserved')
        batch_op.drop_column('reservation_id')
        batch_op.drop_column('order_id')
    
    # Remove POS integration fields from inventory_item
    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        batch_op.drop_column('available_quantity')
        batch_op.drop_column('frozen_quantity')
