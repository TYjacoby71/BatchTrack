
"""Add comprehensive POS integration fields

Revision ID: add_pos_integration_comprehensive
Revises: e04a3508f9f7_initial_schema_with_all_models
Create Date: 2025-06-26 19:17:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_pos_integration_comprehensive'
down_revision = 'e04a3508f9f7_initial_schema_with_all_models'
branch_labels = None
depends_on = None

def upgrade():
    # Add POS integration fields to inventory_history table
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        # Check if columns exist first by trying to add them
        try:
            batch_op.add_column(sa.Column('order_id', sa.String(length=64), nullable=True))
        except:
            pass
        
        try:
            batch_op.add_column(sa.Column('reservation_id', sa.String(length=64), nullable=True))
        except:
            pass
        
        try:
            batch_op.add_column(sa.Column('is_reserved', sa.Boolean(), nullable=True, default=False))
        except:
            pass

    # Add frozen_quantity field to inventory_item table if it doesn't exist
    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        try:
            batch_op.add_column(sa.Column('frozen_quantity', sa.Float(), nullable=True, default=0.0))
        except:
            pass
        
        try:
            batch_op.add_column(sa.Column('available_quantity', sa.Float(), nullable=True, default=0.0))
        except:
            pass

def downgrade():
    # Remove POS integration fields from inventory_history
    with op.batch_alter_table('inventory_history', schema=None) as batch_op:
        try:
            batch_op.drop_column('is_reserved')
        except:
            pass
        
        try:
            batch_op.drop_column('reservation_id')
        except:
            pass
        
        try:
            batch_op.drop_column('order_id')
        except:
            pass

    # Remove frozen_quantity field from inventory_item
    with op.batch_alter_table('inventory_item', schema=None) as batch_op:
        try:
            batch_op.drop_column('available_quantity')
        except:
            pass
        
        try:
            batch_op.drop_column('frozen_quantity')
        except:
            pass
