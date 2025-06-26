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
    # Check if columns already exist, only add if they don't
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('product_sku')]

    with op.batch_alter_table('product_sku', schema=None) as batch_op:
        if 'frozen_quantity' not in existing_columns:
            batch_op.add_column(sa.Column('frozen_quantity', sa.Float(), nullable=True, default=0.0))

        if 'shopify_variant_id' not in existing_columns:
            batch_op.add_column(sa.Column('shopify_variant_id', sa.String(length=64), nullable=True))

        if 'etsy_listing_id' not in existing_columns:
            batch_op.add_column(sa.Column('etsy_listing_id', sa.String(length=64), nullable=True))

        if 'pos_sync_enabled' not in existing_columns:
            batch_op.add_column(sa.Column('pos_sync_enabled', sa.Boolean(), nullable=True, default=False))

    # Add indexes for POS fields (only if they don't exist)
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('product_sku')]

    if 'idx_shopify_variant' not in existing_indexes:
        op.create_index('idx_shopify_variant', 'product_sku', ['shopify_variant_id'], unique=False)

    if 'idx_etsy_listing' not in existing_indexes:
        op.create_index('idx_etsy_listing', 'product_sku', ['etsy_listing_id'], unique=False)

def downgrade():
    # Remove POS integration fields only if they exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('product_sku')]
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('product_sku')]

    # Drop indexes first
    if 'idx_etsy_listing' in existing_indexes:
        op.drop_index('idx_etsy_listing', table_name='product_sku')

    if 'idx_shopify_variant' in existing_indexes:
        op.drop_index('idx_shopify_variant', table_name='product_sku')

    # Drop columns
    with op.batch_alter_table('product_sku', schema=None) as batch_op:
        if 'pos_sync_enabled' in existing_columns:
            batch_op.drop_column('pos_sync_enabled')

        if 'etsy_listing_id' in existing_columns:
            batch_op.drop_column('etsy_listing_id')

        if 'shopify_variant_id' in existing_columns:
            batch_op.drop_column('shopify_variant_id')

        if 'frozen_quantity' in existing_columns:
            batch_op.drop_column('frozen_quantity')