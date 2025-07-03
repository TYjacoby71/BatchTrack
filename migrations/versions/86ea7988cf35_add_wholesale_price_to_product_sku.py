
"""add_wholesale_price_to_product_sku

Revision ID: 86ea7988cf35
Revises: 84207ea041ca
Create Date: 2025-07-03 18:22:45.767440

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '86ea7988cf35'
down_revision = '84207ea041ca'
branch_labels = None
depends_on = None


def upgrade():
    # Add wholesale_price column to product_sku table
    with op.batch_alter_table('product_sku', schema=None) as batch_op:
        batch_op.add_column(sa.Column('wholesale_price', sa.Float(), nullable=True))


def downgrade():
    # Remove wholesale_price column from product_sku table
    with op.batch_alter_table('product_sku', schema=None) as batch_op:
        batch_op.drop_column('wholesale_price')
