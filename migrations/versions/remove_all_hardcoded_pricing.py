
"""remove all hardcoded pricing columns

Revision ID: remove_all_hardcoded_pricing
Revises: 758a11548815
Create Date: 2025-08-18 18:55:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'remove_all_hardcoded_pricing'
down_revision = '758a11548815'
branch_labels = None
depends_on = None

def upgrade():
    """Remove all hardcoded pricing columns - pricing comes from external providers only"""
    
    # Remove pricing columns from subscription_tier
    pricing_columns_to_remove = [
        'fallback_price',
        'stripe_price',
        'stripe_price_id',
        'stripe_price_id_monthly', 
        'stripe_price_id_yearly',
        'stripe_product_id',
        'last_stripe_sync',
        'whop_last_synced',
        'pricing_category',
        'billing_cycle',
        'tier_type',
        'supports_stripe',
        'supports_whop',
        'whop_only',
        'fallback_price_monthly',
        'fallback_price_yearly',
        'stripe_price_monthly',
        'stripe_price_yearly'
    ]
    
    for column in pricing_columns_to_remove:
        try:
            with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
                batch_op.drop_column(column)
            print(f"✅ Removed {column} from subscription_tier")
        except Exception as e:
            print(f"⚠️  Could not remove {column}: {e}")

def downgrade():
    """Add back basic fallback columns if needed"""
    try:
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.add_column(sa.Column('fallback_price', sa.String(16), default='$0'))
    except Exception:
        pass
