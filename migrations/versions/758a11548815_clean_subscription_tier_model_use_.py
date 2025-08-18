
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
    # Clean up any leftover temporary tables first
    connection = op.get_bind()
    try:
        connection.execute(text("DROP TABLE IF EXISTS _alembic_tmp_organization"))
        connection.execute(text("DROP TABLE IF EXISTS _alembic_tmp_subscription_tier"))
    except Exception:
        pass

    # Drop the organization.subscription_tier column if it exists
    try:
        with op.batch_alter_table('organization', schema=None) as batch_op:
            batch_op.drop_column('subscription_tier')
    except Exception:
        pass  # Column might not exist

    # Add missing columns one by one to avoid circular dependencies
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns('subscription_tier')]
    
    # Add columns that don't exist
    if 'user_limit' not in existing_columns:
        op.add_column('subscription_tier', sa.Column('user_limit', sa.Integer(), nullable=False, server_default='1'))
        
    if 'is_customer_facing' not in existing_columns:
        op.add_column('subscription_tier', sa.Column('is_customer_facing', sa.Boolean(), nullable=False, server_default=sa.text('1')))
        
    if 'billing_provider' not in existing_columns:
        op.add_column('subscription_tier', sa.Column('billing_provider', sa.String(length=32), nullable=False, server_default='exempt'))
        
    if 'is_billing_exempt' not in existing_columns:
        op.add_column('subscription_tier', sa.Column('is_billing_exempt', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        
    if 'whop_product_key' not in existing_columns:
        op.add_column('subscription_tier', sa.Column('whop_product_key', sa.String(length=128), nullable=True))

    # Now fix column types in separate batch operations
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        # Fix core column types
        batch_op.alter_column('name',
               existing_type=sa.TEXT(),
               type_=sa.String(length=64),
               nullable=False)
        batch_op.alter_column('key',
               existing_type=sa.TEXT(),
               type_=sa.String(length=32),
               nullable=False)

    # Fix stripe_lookup_key in separate operation
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        batch_op.alter_column('stripe_lookup_key',
               existing_type=sa.TEXT(),
               type_=sa.String(length=128),
               existing_nullable=True)

    # Create constraints in separate operations
    try:
        op.create_unique_constraint('uq_subscription_tier_key', 'subscription_tier', ['key'])
    except Exception:
        pass  # Might already exist
        
    try:
        op.create_unique_constraint('uq_subscription_tier_stripe_lookup_key', 'subscription_tier', ['stripe_lookup_key'])
    except Exception:
        pass
        
    try:
        op.create_unique_constraint('uq_subscription_tier_whop_product_key', 'subscription_tier', ['whop_product_key'])
    except Exception:
        pass

    # Create index
    try:
        op.create_index('ix_subscription_tier_is_billing_exempt', 'subscription_tier', ['is_billing_exempt'], unique=False)
    except Exception:
        pass

    # Drop old columns that shouldn't exist
    columns_to_drop = [
        'grace_period_days', 'max_users', 'stripe_price_id_yearly',
        'max_monthly_batches', 'stripe_product_id', 'stripe_price_id_monthly',
        'stripe_price_id', 'last_billing_sync', 'tier_key'
    ]
    
    for col in columns_to_drop:
        try:
            with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
                batch_op.drop_column(col)
        except Exception:
            pass  # Column might not exist


def downgrade():
    # Simple downgrade - just restore organization.subscription_tier
    try:
        with op.batch_alter_table('organization', schema=None) as batch_op:
            batch_op.add_column(sa.Column('subscription_tier', sa.VARCHAR(length=32), nullable=True))
    except Exception:
        pass
