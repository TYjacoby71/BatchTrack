

"""clean subscription tier model use lookup keys

Revision ID: 758a11548815
Revises: clean_subscription_tier_billing
Create Date: 2025-08-18 18:10:04.813518

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '758a11548815'
down_revision = 'clean_subscription_tier_billing'
branch_labels = None
depends_on = None


def upgrade():
    """Final clean subscription tier structure - no pricing, just tier definitions"""

    connection = op.get_bind()
    inspector = sa.inspect(connection)

    def table_exists(table_name):
        return table_name in inspector.get_table_names()

    def column_exists(table_name, column_name):
        if not table_exists(table_name):
            return False
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns

    print("=== Final Subscription Tier Structure Migration ===")

    # Clean up any leftover temporary tables
    try:
        connection.execute(text("DROP TABLE IF EXISTS _alembic_tmp_organization"))
        connection.execute(text("DROP TABLE IF EXISTS _alembic_tmp_subscription_tier"))
    except Exception:
        pass

    if table_exists('subscription_tier'):
        print("   Found subscription_tier table, cleaning structure...")

        # First, ensure core columns exist with correct types
        core_columns_to_add = [
            ('user_limit', 'INTEGER', '1'),
            ('is_customer_facing', 'BOOLEAN', '1'),
            ('billing_provider', 'VARCHAR(32)', "'exempt'"),
            ('is_billing_exempt', 'BOOLEAN', '0'),
            ('stripe_lookup_key', 'VARCHAR(128)', None),
            ('whop_product_key', 'VARCHAR(128)', None),
        ]

        for col_name, col_type, default_val in core_columns_to_add:
            if not column_exists('subscription_tier', col_name):
                print(f"   Adding {col_name} column...")
                if default_val:
                    op.add_column('subscription_tier', 
                                sa.Column(col_name, 
                                        getattr(sa, col_type.split('(')[0])(*([int(col_type.split('(')[1].split(')')[0])] if '(' in col_type else [])),
                                        nullable=False, 
                                        server_default=default_val))
                else:
                    op.add_column('subscription_tier', 
                                sa.Column(col_name, 
                                        getattr(sa, col_type.split('(')[0])(*([int(col_type.split('(')[1].split(')')[0])] if '(' in col_type else [])),
                                        nullable=True))

        # Remove ALL pricing-related columns
        pricing_columns_to_remove = [
            'fallback_price', 'stripe_price', 'stripe_price_id', 'stripe_price_id_monthly', 
            'stripe_price_id_yearly', 'stripe_product_id', 'last_stripe_sync', 'whop_last_synced',
            'pricing_category', 'billing_cycle', 'tier_type', 'supports_stripe', 'supports_whop',
            'whop_only', 'fallback_price_monthly', 'fallback_price_yearly', 'stripe_price_monthly',
            'stripe_price_yearly', 'grace_period_days', 'max_users', 'max_monthly_batches',
            'last_billing_sync', 'tier_key', 'is_available'
        ]

        for col in pricing_columns_to_remove:
            if column_exists('subscription_tier', col):
                print(f"   Removing pricing column: {col}")
                try:
                    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
                        batch_op.drop_column(col)
                except Exception as e:
                    print(f"   ⚠️  Could not remove {col}: {e}")

        # Fix core column types in batch operations
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            # Ensure proper string lengths
            batch_op.alter_column('name',
                   existing_type=sa.TEXT(),
                   type_=sa.String(length=64),
                   nullable=False)
            batch_op.alter_column('key',
                   existing_type=sa.TEXT(),
                   type_=sa.String(length=32),
                   nullable=False)

        # Create unique constraints (drop existing first to avoid conflicts)
        constraints_to_create = [
            ('uq_subscription_tier_key', ['key']),
            ('uq_subscription_tier_stripe_lookup_key', ['stripe_lookup_key']),
            ('uq_subscription_tier_whop_product_key', ['whop_product_key'])
        ]

        for constraint_name, columns in constraints_to_create:
            try:
                # Try to drop first in case it exists
                op.drop_constraint(constraint_name, 'subscription_tier', type_='unique')
            except Exception:
                pass
            try:
                op.create_unique_constraint(constraint_name, 'subscription_tier', columns)
                print(f"   ✅ Created constraint: {constraint_name}")
            except Exception as e:
                print(f"   ⚠️  Could not create constraint {constraint_name}: {e}")

        # Create index for billing exempt
        try:
            op.create_index('ix_subscription_tier_is_billing_exempt', 'subscription_tier', ['is_billing_exempt'], unique=False)
        except Exception:
            pass

    # Remove subscription_tier column from organization if it exists
    if table_exists('organization') and column_exists('organization', 'subscription_tier'):
        print("   Removing legacy subscription_tier column from organization...")
        try:
            with op.batch_alter_table('organization', schema=None) as batch_op:
                batch_op.drop_column('subscription_tier')
        except Exception as e:
            print(f"   ⚠️  Could not remove organization.subscription_tier: {e}")

    print("✅ Final subscription tier structure migration completed")


def downgrade():
    """Simple downgrade - restore organization.subscription_tier column"""
    try:
        with op.batch_alter_table('organization', schema=None) as batch_op:
            batch_op.add_column(sa.Column('subscription_tier', sa.VARCHAR(length=32), nullable=True))
    except Exception:
        pass
