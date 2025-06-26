
"""Add POS integration fields

Revision ID: add_pos_integration_fields
Revises: e04a3508f9f7_initial_schema_with_all_models
Create Date: 2025-01-26 18:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_pos_integration_fields'
down_revision = 'e04a3508f9f7_initial_schema_with_all_models'
branch_labels = None
depends_on = None

def upgrade():
    # Add POS integration fields to product_sku table
    with op.batch_alter_table('product_sku', schema=None) as batch_op:
        batch_op.add_column(sa.Column('frozen_quantity', sa.Float(), nullable=True, default=0.0))
        batch_op.add_column(sa.Column('shopify_variant_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('etsy_listing_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('pos_sync_enabled', sa.Boolean(), nullable=True, default=False))
        
        # Add indexes for POS fields
        batch_op.create_index('idx_shopify_variant', ['shopify_variant_id'], unique=False)
        batch_op.create_index('idx_etsy_listing', ['etsy_listing_id'], unique=False)

def downgrade():
    # Remove POS integration fields
    with op.batch_alter_table('product_sku', schema=None) as batch_op:
        batch_op.drop_index('idx_etsy_listing')
        batch_op.drop_index('idx_shopify_variant')
        
        batch_op.drop_column('pos_sync_enabled')
        batch_op.drop_column('etsy_listing_id')
        batch_op.drop_column('shopify_variant_id')
        batch_op.drop_column('frozen_quantity')
