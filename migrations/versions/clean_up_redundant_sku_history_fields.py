
"""Clean up redundant fields from ProductSKUHistory

Revision ID: clean_up_redundant_sku_history_fields
Revises: 112dc7f2bfc1
Create Date: 2025-01-03 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'clean_up_redundant_sku_history_fields'
down_revision = '112dc7f2bfc1'
branch_labels = None
depends_on = None

def upgrade():
    # Remove redundant quantity tracking fields
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        batch_op.drop_column('old_quantity')
        batch_op.drop_column('new_quantity')
        batch_op.drop_column('reserved_quantity_change')
        batch_op.drop_column('old_reserved_quantity')
        batch_op.drop_column('new_reserved_quantity')

def downgrade():
    # Add back the columns if needed
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('old_quantity', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('new_quantity', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('reserved_quantity_change', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('old_reserved_quantity', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('new_reserved_quantity', sa.Float(), nullable=True))
