
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
        
        # Remove pricing columns using direct SQL (safer for SQLite)
        pricing_columns_to_remove = [
            'fallback_price', 'stripe_price', 'stripe_price_id', 'stripe_price_id_monthly', 
            'stripe_price_id_yearly', 'stripe_product_id', 'last_stripe_sync', 'whop_last_synced',
            'pricing_category', 'billing_cycle', 'tier_type', 'supports_stripe', 'supports_whop',
            'whop_only', 'fallback_price_monthly', 'fallback_price_yearly', 'stripe_price_monthly',
            'stripe_price_yearly', 'grace_period_days', 'max_users', 'max_monthly_batches',
            'last_billing_sync', 'tier_key', 'is_available'
        ]
        
        # Get current columns to check what actually exists
        current_columns = [col['name'] for col in inspector.get_columns('subscription_tier')]
        
        for col in pricing_columns_to_remove:
            if col in current_columns:
                print(f"   Removing pricing column: {col}")
                try:
                    # Use direct SQL for column removal (more reliable for SQLite)
                    connection.execute(text(f'ALTER TABLE subscription_tier DROP COLUMN "{col}"'))
                except Exception as e:
                    print(f"   ⚠️  Could not remove {col}: {e}")
        
        # Ensure proper column types using batch operations for the critical columns
        print("   Ensuring proper column types...")
        try:
            with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
                # Only alter columns that we know exist and need type fixes
                if 'name' in current_columns:
                    batch_op.alter_column('name',
                           existing_type=sa.TEXT(),
                           type_=sa.String(length=64),
                           nullable=False)
                if 'key' in current_columns:
                    batch_op.alter_column('key',
                           existing_type=sa.TEXT(),
                           type_=sa.String(length=32),
                           nullable=False)
        except Exception as e:
            print(f"   ⚠️  Could not fix column types: {e}")
        
        # Create indexes and constraints using direct SQL
        try:
            # Create unique constraints
            connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_tier_key ON subscription_tier("key")'))
            connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_tier_stripe_lookup_key ON subscription_tier(stripe_lookup_key)'))
            connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_tier_whop_product_key ON subscription_tier(whop_product_key)'))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_subscription_tier_is_billing_exempt ON subscription_tier(is_billing_exempt)'))
            print("   ✅ Created indexes and constraints")
        except Exception as e:
            print(f"   ⚠️  Could not create some indexes: {e}")
    
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
