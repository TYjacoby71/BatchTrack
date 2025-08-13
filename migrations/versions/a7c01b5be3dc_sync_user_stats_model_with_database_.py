"""sync user_stats model with database schema

Revision ID: a7c01b5be3dc
Revises: 6f9bc65166b3
Create Date: 2025-08-13 20:35:28.978000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7c01b5be3dc'
down_revision = '6f9bc65166b3'
branch_labels = None
depends_on = None


def upgrade():
    """Sync user_stats model with database schema"""
    print("=== Syncing user_stats and other model changes ===")

    # Get database connection to check existing columns
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Helper function to check if column exists
    def column_exists(table_name, column_name):
        try:
            columns = inspector.get_columns(table_name)
            return any(col['name'] == column_name for col in columns)
        except Exception:
            return False

    # Helper function to check if table exists
    def table_exists(table_name):
        try:
            return inspector.has_table(table_name)
        except Exception:
            return False

    # Only alter tables that exist and add columns that don't exist
    tables_to_check = [
        'batch_container', 'batch_inventory_log', 'conversion_log',
        'custom_unit_mapping', 'extra_batch_container', 'extra_batch_ingredient',
        'ingredient_category', 'inventory_item', 'product', 'product_sku_history',
        'product_variant', 'recipe', 'recipe_ingredient', 'reservation', 'tag'
    ]

    for table_name in tables_to_check:
        if table_exists(table_name) and not column_exists(table_name, 'organization_id'):
            print(f"   Adding organization_id to {table_name}")
            with op.batch_alter_table(table_name, schema=None) as batch_op:
                batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        elif table_exists(table_name) and column_exists(table_name, 'organization_id'):
            print(f"   Making organization_id nullable in {table_name}")
            with op.batch_alter_table(table_name, schema=None) as batch_op:
                batch_op.alter_column('organization_id', nullable=True)

    # Handle inventory_history table changes
    if table_exists('inventory_history'):
        columns = {col['name']: col for col in inspector.get_columns('inventory_history')}

        with op.batch_alter_table('inventory_history', schema=None) as batch_op:
            if 'change_type' in columns:
                # Update change_type column type and make nullable
                batch_op.alter_column('change_type',
                                    existing_type=sa.VARCHAR(length=32),
                                    type_=sa.String(length=50),
                                    nullable=True)

            if 'quantity_change' in columns:
                batch_op.alter_column('quantity_change', nullable=True)

            if 'organization_id' not in columns:
                batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
            else:
                batch_op.alter_column('organization_id', nullable=True)

    # Handle product_sku table changes
    if table_exists('product_sku'):
        columns = {col['name']: col for col in inspector.get_columns('product_sku')}

        with op.batch_alter_table('product_sku', schema=None) as batch_op:
            # Add missing columns
            if 'id' not in columns:
                batch_op.add_column(sa.Column('id', sa.Integer(), nullable=False, primary_key=True))
            if 'sku' not in columns:
                batch_op.add_column(sa.Column('sku', sa.String(length=255), nullable=True))
            if 'quantity_override' not in columns:
                batch_op.add_column(sa.Column('quantity_override', sa.Float(), nullable=True))

            # Make existing columns nullable
            nullable_columns = ['inventory_item_id', 'product_id', 'variant_id', 'sku_code', 'unit', 'organization_id']
            for col_name in nullable_columns:
                if col_name in columns:
                    batch_op.alter_column(col_name, nullable=True)

        # Add indexes if they don't exist
        indexes = inspector.get_indexes('product_sku')
        index_names = [idx['name'] for idx in indexes]

        if 'ix_product_sku_inventory_item_id' not in index_names:
            op.create_index('ix_product_sku_inventory_item_id', 'product_sku', ['inventory_item_id'])

        # Add unique constraint if it doesn't exist
        unique_constraints = inspector.get_unique_constraints('product_sku')
        sku_unique_exists = any('sku' in uc['column_names'] for uc in unique_constraints)
        if not sku_unique_exists:
            op.create_unique_constraint(None, 'product_sku', ['sku'])

    # Handle unified_inventory_history table changes
    if table_exists('unified_inventory_history'):
        columns = {col['name']: col for col in inspector.get_columns('unified_inventory_history')}

        with op.batch_alter_table('unified_inventory_history', schema=None) as batch_op:
            nullable_columns = ['remaining_quantity', 'quantity_used', 'is_perishable', 'is_reserved', 'organization_id']
            for col_name in nullable_columns:
                if col_name in columns:
                    batch_op.alter_column(col_name, nullable=True)

        # Add indexes for unified_inventory_history
        indexes = inspector.get_indexes('unified_inventory_history')
        index_names = [idx['name'] for idx in indexes]

        new_indexes = [
            ('ix_unified_inventory_history_change_type', ['change_type']),
            ('ix_unified_inventory_history_expiration_date', ['expiration_date']),
            ('ix_unified_inventory_history_fifo_code', ['fifo_code']),
            ('ix_unified_inventory_history_inventory_item_id', ['inventory_item_id']),
            ('ix_unified_inventory_history_timestamp', ['timestamp'])
        ]

        for index_name, columns_list in new_indexes:
            if index_name not in index_names:
                op.create_index(index_name, 'unified_inventory_history', columns_list)

    # Handle unit table changes
    if table_exists('unit'):
        columns = {col['name']: col for col in inspector.get_columns('unit')}
        indexes = inspector.get_indexes('unit')
        index_names = [idx['name'] for idx in indexes]

        with op.batch_alter_table('unit', schema=None) as batch_op:
            if 'symbol' in columns:
                batch_op.alter_column('symbol', nullable=True)

            # Remove old index if it exists
            if 'ix_unit_standard_unique' in index_names:
                batch_op.drop_index('ix_unit_standard_unique')

    # Handle user table changes
    if table_exists('user'):
        columns = {col['name']: col for col in inspector.get_columns('user')}

        with op.batch_alter_table('user', schema=None) as batch_op:
            if 'password_hash' in columns:
                batch_op.alter_column('password_hash', nullable=True)

            # Remove is_verified column if it exists
            if 'is_verified' in columns:
                batch_op.drop_column('is_verified')

    # Handle stripe_event and subscription_tier constraint changes
    if table_exists('stripe_event'):
        unique_constraints = inspector.get_unique_constraints('stripe_event')
        constraint_names = [uc['name'] for uc in unique_constraints]
        indexes = inspector.get_indexes('stripe_event')
        index_names = [idx['name'] for idx in indexes]

        with op.batch_alter_table('stripe_event', schema=None) as batch_op:
            if 'uq_stripe_event_event_id' in constraint_names:
                batch_op.drop_constraint('uq_stripe_event_event_id', type_='unique')

            if 'ix_stripe_event_event_id' in index_names:
                batch_op.drop_index('ix_stripe_event_event_id')
                batch_op.create_index('ix_stripe_event_event_id', ['event_id'], unique=True)

    if table_exists('subscription_tier'):
        columns = {col['name']: col for col in inspector.get_columns('subscription_tier')}
        unique_constraints = inspector.get_unique_constraints('subscription_tier')
        constraint_names = [uc['name'] for uc in unique_constraints]
        indexes = inspector.get_indexes('subscription_tier')
        index_names = [idx['name'] for idx in indexes]

        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            if 'tier_key' in columns:
                batch_op.alter_column('tier_key', nullable=True)

            if 'uq_subscription_tier_tier_key' in constraint_names:
                batch_op.drop_constraint('uq_subscription_tier_tier_key', type_='unique')

            if 'ix_subscription_tier_tier_key' in index_names:
                batch_op.drop_index('ix_subscription_tier_tier_key')
                batch_op.create_index('ix_subscription_tier_tier_key', ['tier_key'], unique=True)

    print("✅ Database schema sync completed")


def downgrade():
    """Reverse the schema sync changes"""
    print("=== Reversing schema sync changes ===")

    # This is a complex downgrade, so we'll implement basic reversals
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def table_exists(table_name):
        try:
            return inspector.has_table(table_name)
        except Exception:
            return False

    # Reverse user table changes
    if table_exists('user'):
        with op.batch_alter_table('user', schema=None) as batch_op:
            batch_op.add_column(sa.Column('is_verified', sa.Boolean(), nullable=True))
            batch_op.alter_column('password_hash', nullable=False)

    print("✅ Schema sync downgrade completed")