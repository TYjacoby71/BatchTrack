
"""add_affected_lot_id_to_unified_inventory_history

Revision ID: ce43ce53da34
Revises: create_inventory_lot
Create Date: 2025-08-21 05:20:31.424600

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ce43ce53da34'
down_revision = 'create_inventory_lot'
branch_labels = None
depends_on = None


def upgrade():
    # Add affected_lot_id column to unified_inventory_history
    op.add_column('unified_inventory_history', sa.Column('affected_lot_id', sa.Integer(), nullable=True))
    
    # Add foreign key constraint for affected_lot_id
    op.create_foreign_key('fk_unified_inventory_history_affected_lot_id', 'unified_inventory_history', 'inventory_lot', ['affected_lot_id'], ['id'])
    
    # Make organization_id NOT NULL in unified_inventory_history
    op.alter_column('unified_inventory_history', 'organization_id', nullable=False)
    
    # Update fifo_code column length in unified_inventory_history
    op.alter_column('unified_inventory_history', 'fifo_code',
                   existing_type=sa.VARCHAR(length=64),
                   type_=sa.String(length=32),
                   existing_nullable=True)

    # Drop the old fifo_code index if it exists
    try:
        op.drop_index('ix_unified_inventory_history_fifo_code', table_name='unified_inventory_history')
    except:
        pass  # Index might not exist
    
    # Update organization billing_status to be NOT NULL
    op.alter_column('organization', 'billing_status',
                   existing_type=sa.VARCHAR(length=50),
                   nullable=False)

    # Update product_sku table structure
    op.alter_column('product_sku', 'id',
                   existing_type=sa.INTEGER(),
                   nullable=False,
                   autoincrement=True)
    
    op.alter_column('product_sku', 'size_label',
                   existing_type=sa.VARCHAR(length=32),
                   type_=sa.String(length=64),
                   nullable=False)
    
    op.alter_column('product_sku', 'sku',
                   existing_type=sa.VARCHAR(length=64),
                   nullable=False)
    
    op.alter_column('product_sku', 'fifo_id',
                   existing_type=sa.VARCHAR(length=64),
                   type_=sa.String(length=32),
                   existing_nullable=True)
    
    op.alter_column('product_sku', 'barcode',
                   existing_type=sa.VARCHAR(length=64),
                   type_=sa.String(length=128),
                   existing_nullable=True)
    
    op.alter_column('product_sku', 'upc',
                   existing_type=sa.VARCHAR(length=64),
                   type_=sa.String(length=32),
                   existing_nullable=True)
    
    op.alter_column('product_sku', 'location_id',
                   existing_type=sa.INTEGER(),
                   type_=sa.String(length=128),
                   existing_nullable=True)

    # Create indexes for product_sku
    op.create_index('idx_active_skus', 'product_sku', ['is_active', 'is_product_active'])
    op.create_index('idx_inventory_item', 'product_sku', ['inventory_item_id'])
    op.create_index('idx_product_variant', 'product_sku', ['product_id', 'variant_id'])
    
    # Create unique constraints with proper names
    op.create_unique_constraint('uq_product_sku_barcode', 'product_sku', ['barcode'])
    op.create_unique_constraint('uq_product_sku_sku_combination', 'product_sku', ['product_id', 'variant_id', 'size_label', 'fifo_id'])
    op.create_unique_constraint('uq_product_sku_upc', 'product_sku', ['upc'])
    op.create_unique_constraint('uq_product_sku_sku', 'product_sku', ['sku'])
    
    # Add foreign key constraints for product_sku
    op.create_foreign_key('fk_product_sku_organization_id', 'product_sku', 'organization', ['organization_id'], ['id'])
    op.create_foreign_key('fk_product_sku_container_id', 'product_sku', 'inventory_item', ['container_id'], ['id'])
    op.create_foreign_key('fk_product_sku_batch_id', 'product_sku', 'batch', ['batch_id'], ['id'])
    op.create_foreign_key('fk_product_sku_inventory_item_id', 'product_sku', 'inventory_item', ['inventory_item_id'], ['id'])
    op.create_foreign_key('fk_product_sku_product_id', 'product_sku', 'product', ['product_id'], ['id'])
    op.create_foreign_key('fk_product_sku_quality_checked_by', 'product_sku', 'user', ['quality_checked_by'], ['id'])
    op.create_foreign_key('fk_product_sku_variant_id', 'product_sku', 'product_variant', ['variant_id'], ['id'])
    op.create_foreign_key('fk_product_sku_created_by', 'product_sku', 'user', ['created_by'], ['id'])

    # Update subscription_tier table
    op.alter_column('subscription_tier', 'id',
                   existing_type=sa.INTEGER(),
                   nullable=False,
                   autoincrement=True)
    
    op.alter_column('subscription_tier', 'name',
                   existing_type=sa.TEXT(),
                   type_=sa.String(length=64),
                   nullable=False)
    
    op.alter_column('subscription_tier', 'user_limit',
                   existing_type=sa.INTEGER(),
                   nullable=False)
    
    op.alter_column('subscription_tier', 'is_customer_facing',
                   existing_type=sa.Boolean(),
                   nullable=False)
    
    op.alter_column('subscription_tier', 'billing_provider',
                   nullable=False)
    
    op.alter_column('subscription_tier', 'stripe_lookup_key',
                   existing_type=sa.TEXT(),
                   type_=sa.String(length=128),
                   existing_nullable=True)
    
    op.alter_column('subscription_tier', 'whop_product_key',
                   existing_type=sa.TEXT(),
                   type_=sa.String(length=128),
                   existing_nullable=True)
    
    op.alter_column('subscription_tier', 'created_at',
                   type_=sa.DateTime(),
                   existing_nullable=True)
    
    op.alter_column('subscription_tier', 'updated_at',
                   type_=sa.DateTime(),
                   existing_nullable=True)

    # Drop old indexes if they exist
    try:
        op.drop_index('ix_subscription_tier_key', table_name='subscription_tier')
    except:
        pass
    try:
        op.drop_index('uq_subscription_tier_name', table_name='subscription_tier')
    except:
        pass
    try:
        op.drop_index('uq_subscription_tier_stripe_lookup_key', table_name='subscription_tier')
    except:
        pass
    
    # Create new unique constraints
    op.create_unique_constraint('uq_subscription_tier_stripe_lookup_key', 'subscription_tier', ['stripe_lookup_key'])
    op.create_unique_constraint('uq_subscription_tier_whop_product_key', 'subscription_tier', ['whop_product_key'])
    op.create_unique_constraint('uq_subscription_tier_name', 'subscription_tier', ['name'])
    
    # Drop the key column from subscription_tier if it exists
    try:
        op.drop_column('subscription_tier', 'key')
    except:
        pass  # Column might not exist


def downgrade():
    # Reverse the changes
    op.add_column('subscription_tier', sa.Column('key', sa.TEXT(), nullable=True))
    
    # Drop constraints
    op.drop_constraint('uq_subscription_tier_name', 'subscription_tier', type_='unique')
    op.drop_constraint('uq_subscription_tier_whop_product_key', 'subscription_tier', type_='unique')
    op.drop_constraint('uq_subscription_tier_stripe_lookup_key', 'subscription_tier', type_='unique')
    
    # Revert subscription_tier columns
    op.alter_column('subscription_tier', 'updated_at',
                   existing_type=sa.DateTime(),
                   existing_nullable=True)
    op.alter_column('subscription_tier', 'created_at',
                   existing_type=sa.DateTime(),
                   existing_nullable=True)
    op.alter_column('subscription_tier', 'whop_product_key',
                   existing_type=sa.String(length=128),
                   type_=sa.TEXT(),
                   existing_nullable=True)
    op.alter_column('subscription_tier', 'stripe_lookup_key',
                   existing_type=sa.String(length=128),
                   type_=sa.TEXT(),
                   existing_nullable=True)
    op.alter_column('subscription_tier', 'billing_provider',
                   nullable=True)
    op.alter_column('subscription_tier', 'is_customer_facing',
                   existing_type=sa.Boolean(),
                   nullable=True)
    op.alter_column('subscription_tier', 'user_limit',
                   existing_type=sa.INTEGER(),
                   nullable=True)
    op.alter_column('subscription_tier', 'name',
                   existing_type=sa.String(length=64),
                   type_=sa.TEXT(),
                   nullable=True)
    op.alter_column('subscription_tier', 'id',
                   existing_type=sa.INTEGER(),
                   nullable=True,
                   autoincrement=True)

    # Drop product_sku constraints and indexes
    op.drop_constraint('fk_product_sku_created_by', 'product_sku', type_='foreignkey')
    op.drop_constraint('fk_product_sku_variant_id', 'product_sku', type_='foreignkey')
    op.drop_constraint('fk_product_sku_quality_checked_by', 'product_sku', type_='foreignkey')
    op.drop_constraint('fk_product_sku_product_id', 'product_sku', type_='foreignkey')
    op.drop_constraint('fk_product_sku_inventory_item_id', 'product_sku', type_='foreignkey')
    op.drop_constraint('fk_product_sku_batch_id', 'product_sku', type_='foreignkey')
    op.drop_constraint('fk_product_sku_container_id', 'product_sku', type_='foreignkey')
    op.drop_constraint('fk_product_sku_organization_id', 'product_sku', type_='foreignkey')
    op.drop_constraint('uq_product_sku_sku', 'product_sku', type_='unique')
    op.drop_constraint('uq_product_sku_upc', 'product_sku', type_='unique')
    op.drop_constraint('uq_product_sku_sku_combination', 'product_sku', type_='unique')
    op.drop_constraint('uq_product_sku_barcode', 'product_sku', type_='unique')
    op.drop_index('idx_product_variant', table_name='product_sku')
    op.drop_index('idx_inventory_item', table_name='product_sku')
    op.drop_index('idx_active_skus', table_name='product_sku')
    
    # Revert product_sku columns
    op.alter_column('product_sku', 'location_id',
                   existing_type=sa.String(length=128),
                   type_=sa.INTEGER(),
                   existing_nullable=True)
    op.alter_column('product_sku', 'upc',
                   existing_type=sa.String(length=32),
                   type_=sa.VARCHAR(length=64),
                   existing_nullable=True)
    op.alter_column('product_sku', 'barcode',
                   existing_type=sa.String(length=128),
                   type_=sa.VARCHAR(length=64),
                   existing_nullable=True)
    op.alter_column('product_sku', 'fifo_id',
                   existing_type=sa.String(length=32),
                   type_=sa.VARCHAR(length=64),
                   existing_nullable=True)
    op.alter_column('product_sku', 'sku',
                   existing_type=sa.VARCHAR(length=64),
                   nullable=True)
    op.alter_column('product_sku', 'size_label',
                   existing_type=sa.String(length=64),
                   type_=sa.VARCHAR(length=32),
                   nullable=True)
    op.alter_column('product_sku', 'id',
                   existing_type=sa.INTEGER(),
                   nullable=True,
                   autoincrement=True)

    # Revert organization changes
    op.alter_column('organization', 'billing_status',
                   existing_type=sa.VARCHAR(length=50),
                   nullable=True)

    # Revert unified_inventory_history changes
    op.drop_constraint('fk_unified_inventory_history_affected_lot_id', 'unified_inventory_history', type_='foreignkey')
    op.alter_column('unified_inventory_history', 'organization_id',
                   existing_type=sa.INTEGER(),
                   nullable=True)
    op.alter_column('unified_inventory_history', 'fifo_code',
                   existing_type=sa.String(length=32),
                   type_=sa.VARCHAR(length=64),
                   existing_nullable=True)
    op.drop_column('unified_inventory_history', 'affected_lot_id')
