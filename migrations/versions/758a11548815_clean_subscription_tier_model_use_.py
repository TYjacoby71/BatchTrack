
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
    # Clean up any leftover temporary tables
    connection = op.get_bind()
    try:
        connection.execute(text("DROP TABLE IF EXISTS _alembic_tmp_organization"))
        connection.execute(text("DROP TABLE IF EXISTS _alembic_tmp_subscription_tier"))
    except Exception:
        pass

    # Drop the organization.subscription_tier column first
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.drop_column('subscription_tier')

    # Now fix the subscription_tier table
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        # Ensure core columns are correct
        batch_op.alter_column('name',
               existing_type=sa.TEXT(),
               type_=sa.String(length=64),
               nullable=False)
        batch_op.alter_column('key',
               existing_type=sa.TEXT(),
               type_=sa.String(length=32),
               nullable=False)
        
        # Fix stripe_lookup_key type
        batch_op.alter_column('stripe_lookup_key',
               existing_type=sa.TEXT(),
               type_=sa.String(length=128),
               existing_nullable=True)
               
        # Add missing columns with proper defaults
        try:
            batch_op.add_column(sa.Column('user_limit', sa.Integer(), nullable=False, server_default='1'))
        except Exception:
            pass  # Column might already exist
            
        try:
            batch_op.add_column(sa.Column('is_customer_facing', sa.Boolean(), nullable=False, server_default=sa.text('1')))
        except Exception:
            pass
            
        try:
            batch_op.add_column(sa.Column('billing_provider', sa.String(length=32), nullable=False, server_default='exempt'))
        except Exception:
            pass
            
        try:
            batch_op.add_column(sa.Column('is_billing_exempt', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        except Exception:
            pass
            
        try:
            batch_op.add_column(sa.Column('whop_product_key', sa.String(length=128), nullable=True))
        except Exception:
            pass

        # Create properly named unique constraints
        try:
            batch_op.create_unique_constraint('uq_subscription_tier_key', ['key'])
        except Exception:
            pass  # Might already exist
            
        try:
            batch_op.create_unique_constraint('uq_subscription_tier_stripe_lookup_key', ['stripe_lookup_key'])
        except Exception:
            pass
            
        try:
            batch_op.create_unique_constraint('uq_subscription_tier_whop_product_key', ['whop_product_key'])
        except Exception:
            pass

        # Create index
        try:
            batch_op.create_index('ix_subscription_tier_is_billing_exempt', ['is_billing_exempt'], unique=False)
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
                batch_op.drop_column(col)
            except Exception:
                pass  # Column might not exist


def downgrade():
    # Simple downgrade - just restore organization.subscription_tier
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.add_column(sa.Column('subscription_tier', sa.VARCHAR(length=32), nullable=True))
