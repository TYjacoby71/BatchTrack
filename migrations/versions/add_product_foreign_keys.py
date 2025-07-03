
"""Add product_id and variant_id columns to product_sku table

Revision ID: add_product_foreign_keys  
Revises: f1fffb4bc721
Create Date: 2025-07-03 21:15:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_product_foreign_keys'
down_revision = 'f1fffb4bc721'
branch_labels = None
depends_on = None

def upgrade():
    # Add the missing columns to the existing product_sku table
    with op.batch_alter_table('product_sku', schema=None) as batch_op:
        batch_op.add_column(sa.Column('product_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('variant_id', sa.Integer(), nullable=True))

def downgrade():
    # Remove the added columns
    with op.batch_alter_table('product_sku', schema=None) as batch_op:
        batch_op.drop_column('variant_id')
        batch_op.drop_column('product_id')
