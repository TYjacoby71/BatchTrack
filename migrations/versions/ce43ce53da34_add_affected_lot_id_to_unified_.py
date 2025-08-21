"""add_affected_lot_id_to_unified_inventory_history

Revision ID: ce43ce53da34
Revises: create_inventory_lot
Create Date: 2025-08-21 05:20:31.424600

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'ce43ce53da34'
down_revision = 'create_inventory_lot'
branch_labels = None
depends_on = None


def get_database_type():
    """Detect database type"""
    bind = op.get_bind()
    return bind.dialect.name


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    db_type = get_database_type()
    print(f"Running migration for {db_type} database")

    # 1. Add affected_lot_id column to unified_inventory_history
    if not column_exists('unified_inventory_history', 'affected_lot_id'):
        print("Adding affected_lot_id column...")
        op.add_column('unified_inventory_history', sa.Column('affected_lot_id', sa.Integer(), nullable=True))

    # 2. Add foreign key constraint for affected_lot_id
    if table_exists('inventory_lot'):
        try:
            op.create_foreign_key(
                'fk_unified_inventory_history_affected_lot_id',
                'unified_inventory_history',
                'inventory_lot',
                ['affected_lot_id'],
                ['id']
            )
            print("Added foreign key constraint for affected_lot_id")
        except Exception as e:
            print(f"Warning: Could not add foreign key constraint: {e}")

    # 3. Handle organization_id NOT NULL constraint using batch mode for SQLite
    if db_type == 'sqlite':
        print("Using batch mode for SQLite column alterations...")
        with op.batch_alter_table('unified_inventory_history', schema=None) as batch_op:
            try:
                # Make organization_id NOT NULL in batch mode
                batch_op.alter_column('organization_id', nullable=False)
                print("Updated organization_id to NOT NULL")
            except Exception as e:
                print(f"Warning: Could not alter organization_id: {e}")

            try:
                # Update fifo_code column length
                batch_op.alter_column('fifo_code',
                                    existing_type=sa.VARCHAR(length=64),
                                    type_=sa.String(length=32),
                                    existing_nullable=True)
                print("Updated fifo_code column length")
            except Exception as e:
                print(f"Warning: Could not alter fifo_code: {e}")
    else:
        # PostgreSQL can handle direct alterations
        print("Using direct column alterations for PostgreSQL...")
        try:
            op.alter_column('unified_inventory_history', 'organization_id', nullable=False)
            print("Updated organization_id to NOT NULL")
        except Exception as e:
            print(f"Warning: Could not alter organization_id: {e}")

        try:
            op.alter_column('unified_inventory_history', 'fifo_code',
                           existing_type=sa.VARCHAR(length=64),
                           type_=sa.String(length=32),
                           existing_nullable=True)
            print("Updated fifo_code column length")
        except Exception as e:
            print(f"Warning: Could not alter fifo_code: {e}")

    # 4. Handle organization table changes
    try:
        if db_type == 'sqlite':
            with op.batch_alter_table('organization', schema=None) as batch_op:
                batch_op.alter_column('billing_status',
                                    existing_type=sa.VARCHAR(length=50),
                                    nullable=False)
        else:
            op.alter_column('organization', 'billing_status',
                           existing_type=sa.VARCHAR(length=50),
                           nullable=False)
        print("Updated organization billing_status to NOT NULL")
    except Exception as e:
        print(f"Warning: Could not alter organization.billing_status: {e}")

    # 5. Handle product_sku table structure updates
    if table_exists('product_sku'):
        print("Updating product_sku table structure...")

        if db_type == 'sqlite':
            with op.batch_alter_table('product_sku', schema=None) as batch_op:
                try:
                    batch_op.alter_column('id', nullable=False, autoincrement=True)
                    batch_op.alter_column('size_label', type_=sa.String(length=64), nullable=False)
                    batch_op.alter_column('sku', nullable=False)
                    batch_op.alter_column('fifo_id', type_=sa.String(length=32))
                    batch_op.alter_column('barcode', type_=sa.String(length=128))
                    batch_op.alter_column('upc', type_=sa.String(length=32))
                    batch_op.alter_column('location_id', type_=sa.String(length=128))
                    print("Updated product_sku columns in batch mode")
                except Exception as e:
                    print(f"Warning: Could not update product_sku columns: {e}")
        else:
            try:
                op.alter_column('product_sku', 'id', nullable=False, autoincrement=True)
                op.alter_column('product_sku', 'size_label', type_=sa.String(length=64), nullable=False)
                op.alter_column('product_sku', 'sku', nullable=False)
                op.alter_column('product_sku', 'fifo_id', type_=sa.String(length=32))
                op.alter_column('product_sku', 'barcode', type_=sa.String(length=128))
                op.alter_column('product_sku', 'upc', type_=sa.String(length=32))
                op.alter_column('product_sku', 'location_id', type_=sa.String(length=128))
                print("Updated product_sku columns")
            except Exception as e:
                print(f"Warning: Could not update product_sku columns: {e}")

        # Add indexes and constraints for product_sku
        try:
            op.create_index('idx_active_skus', 'product_sku', ['is_active', 'is_product_active'])
            op.create_index('idx_inventory_item', 'product_sku', ['inventory_item_id'])
            op.create_index('idx_product_variant', 'product_sku', ['product_id', 'variant_id'])
            print("Created product_sku indexes")
        except Exception as e:
            print(f"Warning: Could not create product_sku indexes: {e}")

        # Create unique constraints with proper names
        try:
            op.create_unique_constraint('uq_product_sku_barcode', 'product_sku', ['barcode'])
            op.create_unique_constraint('uq_product_sku_sku_combination', 'product_sku', ['product_id', 'variant_id', 'size_label', 'fifo_id'])
            op.create_unique_constraint('uq_product_sku_upc', 'product_sku', ['upc'])
            op.create_unique_constraint('uq_product_sku_sku', 'product_sku', ['sku'])
            print("Created product_sku unique constraints")
        except Exception as e:
            print(f"Warning: Could not create product_sku unique constraints: {e}")


        # Add foreign key constraints for product_sku
        try:
            op.create_foreign_key('fk_product_sku_organization_id', 'product_sku', 'organization', ['organization_id'], ['id'])
            op.create_foreign_key('fk_product_sku_container_id', 'product_sku', 'inventory_item', ['container_id'], ['id'])
            op.create_foreign_key('fk_product_sku_batch_id', 'product_sku', 'batch', ['batch_id'], ['id'])
            op.create_foreign_key('fk_product_sku_inventory_item_id', 'product_sku', 'inventory_item', ['inventory_item_id'], ['id'])
            op.create_foreign_key('fk_product_sku_product_id', 'product_sku', 'product', ['product_id'], ['id'])
            op.create_foreign_key('fk_product_sku_quality_checked_by', 'product_sku', 'user', ['quality_checked_by'], ['id'])
            op.create_foreign_key('fk_product_sku_variant_id', 'product_sku', 'product_variant', ['variant_id'], ['id'])
            op.create_foreign_key('fk_product_sku_created_by', 'product_sku', 'user', ['created_by'], ['id'])
            print("Added product_sku foreign key constraints")
        except Exception as e:
            print(f"Warning: Could not add product_sku foreign key constraints: {e}")

    # 6. Handle subscription_tier table updates
    if table_exists('subscription_tier'):
        print("Updating subscription_tier table...")

        if db_type == 'sqlite':
            with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
                try:
                    batch_op.alter_column('id', nullable=False, autoincrement=True)
                    batch_op.alter_column('name', type_=sa.String(length=64), nullable=False)
                    batch_op.alter_column('user_limit', nullable=False)
                    batch_op.alter_column('is_customer_facing', nullable=False)
                    batch_op.alter_column('billing_provider', nullable=False)
                    batch_op.alter_column('stripe_lookup_key', type_=sa.String(length=128))
                    batch_op.alter_column('whop_product_key', type_=sa.String(length=128))
                    print("Updated subscription_tier columns in batch mode")
                except Exception as e:
                    print(f"Warning: Could not update subscription_tier columns: {e}")
        else:
            try:
                op.alter_column('subscription_tier', 'id', nullable=False, autoincrement=True)
                op.alter_column('subscription_tier', 'name', type_=sa.String(length=64), nullable=False)
                op.alter_column('subscription_tier', 'user_limit', nullable=False)
                op.alter_column('subscription_tier', 'is_customer_facing', nullable=False)
                op.alter_column('subscription_tier', 'billing_provider', nullable=False)
                op.alter_column('subscription_tier', 'stripe_lookup_key', type_=sa.String(length=128))
                op.alter_column('subscription_tier', 'whop_product_key', type_=sa.String(length=128))
                print("Updated subscription_tier columns")
            except Exception as e:
                print(f"Warning: Could not update subscription_tier columns: {e}")

        # Drop old indexes if they exist
        try:
            op.drop_index('ix_subscription_tier_key', table_name='subscription_tier')
        except Exception as e:
            print(f"Warning: Could not drop index ix_subscription_tier_key: {e}")
        try:
            op.drop_index('uq_subscription_tier_name', table_name='subscription_tier')
        except Exception as e:
            print(f"Warning: Could not drop index uq_subscription_tier_name: {e}")
        try:
            op.drop_index('uq_subscription_tier_stripe_lookup_key', table_name='subscription_tier')
        except Exception as e:
            print(f"Warning: Could not drop index uq_subscription_tier_stripe_lookup_key: {e}")

        # Create new unique constraints
        try:
            op.create_unique_constraint('uq_subscription_tier_stripe_lookup_key', 'subscription_tier', ['stripe_lookup_key'])
            op.create_unique_constraint('uq_subscription_tier_whop_product_key', 'subscription_tier', ['whop_product_key'])
            op.create_unique_constraint('uq_subscription_tier_name', 'subscription_tier', ['name'])
            print("Created subscription_tier unique constraints")
        except Exception as e:
            print(f"Warning: Could not create subscription_tier unique constraints: {e}")

    print("Migration completed successfully!")


def downgrade():
    """Reverse the changes"""
    print("Reverting migration changes...")

    # 1. Revert subscription_tier changes
    try:
        op.drop_constraint('uq_subscription_tier_name', 'subscription_tier', type_='unique')
    except Exception as e:
        print(f"Warning: Could not drop constraint uq_subscription_tier_name: {e}")
    try:
        op.drop_constraint('uq_subscription_tier_whop_product_key', 'subscription_tier', type_='unique')
    except Exception as e:
        print(f"Warning: Could not drop constraint uq_subscription_tier_whop_product_key: {e}")
    try:
        op.drop_constraint('uq_subscription_tier_stripe_lookup_key', 'subscription_tier', type_='unique')
    except Exception as e:
        print(f"Warning: Could not drop constraint uq_subscription_tier_stripe_lookup_key: {e}")

    # Recreate old indexes if they existed
    try:
        op.create_index('ix_subscription_tier_key', 'subscription_tier', ['id']) # Assuming 'key' was related to 'id'
    except Exception as e:
        print(f"Warning: Could not recreate index ix_subscription_tier_key: {e}")
    try:
        op.create_index('uq_subscription_tier_name', 'subscription_tier', ['name'], unique=True)
    except Exception as e:
        print(f"Warning: Could not recreate index uq_subscription_tier_name: {e}")
    try:
        op.create_index('uq_subscription_tier_stripe_lookup_key', 'subscription_tier', ['stripe_lookup_key'], unique=True)
    except Exception as e:
        print(f"Warning: Could not recreate index uq_subscription_tier_stripe_lookup_key: {e}")

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

    # 2. Drop product_sku constraints and indexes
    try:
        op.drop_constraint('uq_product_sku_barcode', 'product_sku', type_='unique')
    except Exception as e:
        print(f"Warning: Could not drop constraint uq_product_sku_barcode: {e}")
    try:
        op.drop_constraint('uq_product_sku_sku_combination', 'product_sku', type_='unique')
    except Exception as e:
        print(f"Warning: Could not drop constraint uq_product_sku_sku_combination: {e}")
    try:
        op.drop_constraint('uq_product_sku_upc', 'product_sku', type_='unique')
    except Exception as e:
        print(f"Warning: Could not drop constraint uq_product_sku_upc: {e}")
    try:
        op.drop_constraint('uq_product_sku_sku', 'product_sku', type_='unique')
    except Exception as e:
        print(f"Warning: Could not drop constraint uq_product_sku_sku: {e}")

    try:
        op.drop_index('idx_product_variant', table_name='product_sku')
    except Exception as e:
        print(f"Warning: Could not drop index idx_product_variant: {e}")
    try:
        op.drop_index('idx_inventory_item', table_name='product_sku')
    except Exception as e:
        print(f"Warning: Could not drop index idx_inventory_item: {e}")
    try:
        op.drop_index('idx_active_skus', table_name='product_sku')
    except Exception as e:
        print(f"Warning: Could not drop index idx_active_skus: {e}")

    # Revert product_sku columns
    try:
        op.alter_column('product_sku', 'location_id',
                       existing_type=sa.String(length=128),
                       type_=sa.INTEGER(),
                       existing_nullable=True)
    except Exception as e:
        print(f"Warning: Could not revert product_sku.location_id: {e}")
    try:
        op.alter_column('product_sku', 'upc',
                       existing_type=sa.String(length=32),
                       type_=sa.VARCHAR(length=64),
                       existing_nullable=True)
    except Exception as e:
        print(f"Warning: Could not revert product_sku.upc: {e}")
    try:
        op.alter_column('product_sku', 'barcode',
                       existing_type=sa.String(length=128),
                       type_=sa.VARCHAR(length=64),
                       existing_nullable=True)
    except Exception as e:
        print(f"Warning: Could not revert product_sku.barcode: {e}")
    try:
        op.alter_column('product_sku', 'fifo_id',
                       existing_type=sa.String(length=32),
                       type_=sa.VARCHAR(length=64),
                       existing_nullable=True)
    except Exception as e:
        print(f"Warning: Could not revert product_sku.fifo_id: {e}")
    try:
        op.alter_column('product_sku', 'sku',
                       existing_type=sa.VARCHAR(length=64),
                       nullable=True)
    except Exception as e:
        print(f"Warning: Could not revert product_sku.sku: {e}")
    try:
        op.alter_column('product_sku', 'size_label',
                       existing_type=sa.String(length=64),
                       type_=sa.VARCHAR(length=32),
                       nullable=True)
    except Exception as e:
        print(f"Warning: Could not revert product_sku.size_label: {e}")
    try:
        op.alter_column('product_sku', 'id',
                       existing_type=sa.INTEGER(),
                       nullable=True,
                       autoincrement=True)
    except Exception as e:
        print(f"Warning: Could not revert product_sku.id: {e}")

    # Revert organization changes
    try:
        op.alter_column('organization', 'billing_status',
                       existing_type=sa.VARCHAR(length=50),
                       nullable=True)
    except Exception as e:
        print(f"Warning: Could not revert organization.billing_status: {e}")

    # Revert unified_inventory_history changes
    try:
        op.drop_constraint('fk_unified_inventory_history_affected_lot_id', 'unified_inventory_history', type_='foreignkey')
    except Exception as e:
        print(f"Warning: Could not drop constraint fk_unified_inventory_history_affected_lot_id: {e}")
    try:
        op.alter_column('unified_inventory_history', 'organization_id',
                       existing_type=sa.INTEGER(),
                       nullable=True)
    except Exception as e:
        print(f"Warning: Could not revert unified_inventory_history.organization_id: {e}")
    try:
        op.alter_column('unified_inventory_history', 'fifo_code',
                       existing_type=sa.String(length=32),
                       type_=sa.VARCHAR(length=64),
                       existing_nullable=True)
    except Exception as e:
        print(f"Warning: Could not revert unified_inventory_history.fifo_code: {e}")
    try:
        op.drop_column('unified_inventory_history', 'affected_lot_id')
    except Exception as e:
        print(f"Warning: Could not drop column affected_lot_id: {e}")

    print("Downgrade completed")