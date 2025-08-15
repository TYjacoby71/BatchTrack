
"""clean subscription tier billing structure

Revision ID: clean_subscription_tier_billing
Revises: 57d6ce45a761
Create Date: 2025-08-14 23:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'clean_subscription_tier_billing'
down_revision = '57d6ce45a761'
branch_labels = None
depends_on = None

def upgrade():
    # Helper function to check if column exists
    def column_exists(table_name, column_name):
        inspector = sa.inspect(op.get_bind())
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    
    # First, update any NULL billing_provider values to 'exempt'
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE subscription_tier SET billing_provider = 'exempt' WHERE billing_provider IS NULL")
    )
    
    # Add new billing columns only if they don't exist
    if not column_exists('subscription_tier', 'is_billing_exempt'):
        op.add_column('subscription_tier', sa.Column('is_billing_exempt', sa.Boolean(), default=False))
    
    # For SQLite, we need to handle the billing_provider column change carefully
    # Check if billing_provider allows NULL currently
    inspector = sa.inspect(connection)
    columns = inspector.get_columns('subscription_tier')
    billing_provider_col = next((col for col in columns if col['name'] == 'billing_provider'), None)
    
    # Only alter if the column exists and is nullable
    if billing_provider_col and billing_provider_col.get('nullable', True):
        # Use a direct SQL approach for SQLite compatibility
        connection.execute(sa.text("""
            CREATE TABLE subscription_tier_new AS 
            SELECT 
                id,
                name,
                "key",
                description,
                user_limit,
                is_customer_facing,
                is_available,
                stripe_lookup_key,
                created_at,
                updated_at,
                whop_product_key,
                fallback_price,
                last_billing_sync,
                grace_period_days,
                tier_type,
                COALESCE(billing_provider, 'exempt') as billing_provider,
                tier_key,
                max_users,
                max_monthly_batches,
                stripe_product_id,
                stripe_price_id,
                stripe_price_id_monthly,
                stripe_price_id_yearly,
                is_billing_exempt
            FROM subscription_tier;
        """))
        
        # Drop old table and rename new one
        connection.execute(sa.text("DROP TABLE subscription_tier;"))
        connection.execute(sa.text("ALTER TABLE subscription_tier_new RENAME TO subscription_tier;"))
        
        # Recreate unique constraint on key
        connection.execute(sa.text("CREATE UNIQUE INDEX ix_subscription_tier_key ON subscription_tier(\"key\");"))
    
    # Remove deprecated columns if they exist (these should be safe to drop)
    if column_exists('subscription_tier', 'is_available'):
        op.drop_column('subscription_tier', 'is_available')
        
    if column_exists('subscription_tier', 'tier_type'):
        op.drop_column('subscription_tier', 'tier_type')

def downgrade():
    # Add back deprecated columns
    op.add_column('subscription_tier', sa.Column('is_available', sa.Boolean(), default=True))
    op.add_column('subscription_tier', sa.Column('tier_type', sa.String(32), default='paid'))
    
    # Make billing_provider nullable again (SQLite doesn't support this easily, so we'll skip)
    
    # Remove new columns
    op.drop_column('subscription_tier', 'is_billing_exempt')
