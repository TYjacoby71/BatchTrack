
"""Remove original_quantity from product_sku_history

Revision ID: remove_original_quantity
Revises: aa271449bf33
Create Date: 2025-01-07 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'remove_original_quantity'
down_revision = 'aa271449bf33'
branch_labels = None
depends_on = None

def upgrade():
    # Remove original_quantity column from product_sku_history
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        batch_op.drop_column('original_quantity')

def downgrade():
    # Add back original_quantity column
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('original_quantity', sa.Float(), nullable=True))
