"""clean subscription tier model use lookup keys

Revision ID: 758a11548815
Revises: clean_subscription_tier_billing
Create Date: 2025-08-18 18:10:04.813518

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect

# revision identifiers, used by Alembic.
revision = '758a11548815'
down_revision = 'clean_subscription_tier_billing'
branch_labels = None
depends_on = None


def upgrade():
    """Final clean subscription tier structure - no pricing, just tier definitions"""

    connection = op.get_bind()
    # Initial inspector for table existence checks
    inspector_initial = sa.inspect(connection)

    def table_exists(table_name):
        return table_name in inspector_initial.get_table_names()

    def column_exists(table_name, column_name):
        """Check if a column exists in a table"""
        if not table_exists(table_name):
            return False
        try:
            bind = op.get_bind()
            # Check if we're in a failed transaction state
            try:
                bind.execute(text("SELECT 1"))
            except Exception as e:
                if "aborted" in str(e).lower():
                    print(f"   ⚠️  Transaction aborted, rolling back...")
                    bind.rollback()
                    bind = op.get_bind()  # Get fresh connection

            inspector = inspect(bind)
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception as e:
            print(f"   ⚠️  Could not check column existence for {table_name}.{column_name}: {e}")
            return False

    print("=== Final Subscription Tier Structure Migration ===")

    # Clean up any leftover temporary tables
    try:
        connection.execute(text("DROP TABLE IF EXISTS _alembic_tmp_subscription_tier"))
        connection.execute(text("DROP TABLE IF EXISTS _alembic_tmp_organization"))
    except Exception:
        pass

    if table_exists('subscription_tier'):
        print("   Found subscription_tier table, cleaning structure...")

        # First, ensure required columns exist with proper defaults
        if not column_exists('subscription_tier', 'user_limit'):
            print("   Adding user_limit column...")
            op.add_column('subscription_tier', sa.Column('user_limit', sa.Integer, nullable=False, server_default='1'))

        if not column_exists('subscription_tier', 'is_customer_facing'):
            print("   Adding is_customer_facing column...")
            op.add_column('subscription_tier', sa.Column('is_customer_facing', sa.Boolean, nullable=False, server_default='1'))

        if not column_exists('subscription_tier', 'is_billing_exempt'):
            print("   Adding is_billing_exempt column...")
            op.add_column('subscription_tier', sa.Column('is_billing_exempt', sa.Boolean, nullable=False, server_default='0'))

        if not column_exists('subscription_tier', 'stripe_lookup_key'):
            print("   Adding stripe_lookup_key column...")
            op.add_column('subscription_tier', sa.Column('stripe_lookup_key', sa.String(128), nullable=True))

        if not column_exists('subscription_tier', 'whop_product_key'):
            print("   Adding whop_product_key column...")
            op.add_column('subscription_tier', sa.Column('whop_product_key', sa.String(128), nullable=True))

        # Add tier limit columns
        tier_limit_columns = [
            ('max_users', 'Legacy max users limit'),
            ('max_recipes', 'Maximum recipes allowed'),
            ('max_batches', 'Maximum batches allowed'),
            ('max_products', 'Maximum products allowed'),
            ('max_batchbot_requests', 'Maximum AI requests allowed'),
            ('max_monthly_batches', 'Maximum monthly batches allowed')
        ]

        for col_name, description in tier_limit_columns:
            if not column_exists('subscription_tier', col_name):
                print(f"   Adding {col_name} column...")
                op.add_column('subscription_tier', sa.Column(col_name, sa.Integer, nullable=True))

        # Ensure billing_provider exists and has proper type and default
        if column_exists('subscription_tier', 'billing_provider'):
            print("   Updating billing_provider defaults...")
            connection.execute(text("UPDATE subscription_tier SET billing_provider = 'exempt' WHERE billing_provider IS NULL OR billing_provider = ''"))
        else:
            print("   Adding billing_provider column...")
            op.add_column('subscription_tier', sa.Column('billing_provider', sa.String(32), nullable=False, server_default="'exempt'"))

        # Remove deprecated pricing columns; keep structural columns to avoid churn
        # DO NOT drop: 'tier_type', 'billing_provider', 'tier_key', limits columns, etc.
        columns_to_remove = [
            'fallback_price', 'stripe_price', 'stripe_price_id', 'stripe_price_id_monthly',
            'stripe_price_id_yearly', 'stripe_product_id', 'last_stripe_sync', 'whop_last_synced',
            'pricing_category', 'billing_cycle', 'supports_stripe', 'supports_whop', 'whop_only',
            'fallback_price_monthly', 'fallback_price_yearly', 'stripe_price_monthly', 'stripe_price_yearly',
            'is_available'
        ]

        # Get current columns to check what actually exists
        current_columns = [col['name'] for col in inspector_initial.get_columns('subscription_tier')]

        # Drop columns safely using batch mode (SQLite-safe); only if they exist
        cols_to_drop_now = [c for c in columns_to_remove if c in current_columns]
        if cols_to_drop_now:
            try:
                with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
                    for col in cols_to_drop_now:
                        print(f"   Removing deprecated column: {col}")
                        try:
                            batch_op.drop_column(col)
                        except Exception as e:
                            print(f"   ⚠️  Could not remove {col}: {e}")
            except Exception as outer_e:
                print(f"   ⚠️  Batch drop failed: {outer_e}")

        # Ensure proper column types and constraints
        print("   Ensuring proper column types...")
        if column_exists('subscription_tier', 'key'):
            # First, update any NULL key values with a default
            try:
                bind = op.get_bind()
                # Test transaction state first
                try:
                    bind.execute(text("SELECT 1"))
                except Exception as test_e:
                    if "aborted" in str(test_e).lower():
                        print("   ⚠️  Transaction aborted, rolling back...")
                        bind.rollback()
                        bind = op.get_bind()

                # Fix NULL key values (dialect-aware CAST)
                dialect = bind.dialect.name
                if dialect == 'postgresql':
                    update_sql = """
                        UPDATE subscription_tier 
                        SET key = COALESCE(key, 'tier_' || id::text) 
                        WHERE key IS NULL
                    """
                else:
                    update_sql = """
                        UPDATE subscription_tier 
                        SET key = COALESCE(key, 'tier_' || CAST(id AS TEXT)) 
                        WHERE key IS NULL
                    """
                bind.execute(text(update_sql))
                print("   ✅ Fixed NULL key values")

                # Now make it NOT NULL
                op.alter_column('subscription_tier', 'key',
                              existing_type=sa.String(32),
                              nullable=False)
                print("   ✅ Set key column as NOT NULL")

            except Exception as e:
                print(f"   ⚠️  Could not fix key column: {e}")
                # Rollback and continue
                try:
                    bind = op.get_bind()
                    bind.rollback()
                except:
                    pass

        # Create indexes
        print("   Creating indexes...")
        try:
            # Check transaction state before creating indexes
            bind = op.get_bind()
            try:
                bind.execute(text("SELECT 1"))
            except Exception as test_e:
                if "aborted" in str(test_e).lower():
                    print("   ⚠️  Transaction aborted, rolling back before creating indexes...")
                    bind.rollback()
                    bind = op.get_bind()

            op.create_index('uq_subscription_tier_key', 'subscription_tier', ['key'], unique=True, if_not_exists=True)
            print("   ✅ Created unique key index")
            op.create_index('idx_subscription_tier_billing_provider', 'subscription_tier', ['billing_provider'], if_not_exists=True)
            print("   ✅ Created billing provider index")
        except Exception as e:
            print(f"   ⚠️  Could not create some indexes: {e}")
            # Try to rollback and continue
            try:
                bind = op.get_bind()
                bind.rollback()
            except:
                pass

    # Remove subscription_tier column from organization if it exists
    if table_exists('organization') and column_exists('organization', 'subscription_tier'):
        print("   Removing legacy subscription_tier column from organization...")
        try:
            connection.execute(text('ALTER TABLE organization DROP COLUMN subscription_tier'))
        except Exception as e:
            print(f"   ⚠️  Could not remove organization.subscription_tier: {e}")

    print("✅ Final subscription tier structure migration completed")


def downgrade():
    """Simple downgrade - restore organization.subscription_tier column"""
    try:
        op.add_column('organization', sa.Column('subscription_tier', sa.VARCHAR(length=32), nullable=True))
    except Exception:
        pass