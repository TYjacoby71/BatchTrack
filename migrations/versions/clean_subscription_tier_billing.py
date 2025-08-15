
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
    # Add new billing columns
    op.add_column('subscription_tier', sa.Column('is_billing_exempt', sa.Boolean(), default=False))
    
    # Update billing_provider to be non-nullable with default
    op.alter_column('subscription_tier', 'billing_provider', 
                   existing_type=sa.String(32),
                   nullable=False,
                   server_default='exempt')
    
    # Remove deprecated columns if they exist
    try:
        op.drop_column('subscription_tier', 'is_available')
    except:
        pass  # Column may not exist
        
    try:
        op.drop_column('subscription_tier', 'tier_type')
    except:
        pass  # Column may not exist

def downgrade():
    # Add back deprecated columns
    op.add_column('subscription_tier', sa.Column('is_available', sa.Boolean(), default=True))
    op.add_column('subscription_tier', sa.Column('tier_type', sa.String(32), default='paid'))
    
    # Make billing_provider nullable again
    op.alter_column('subscription_tier', 'billing_provider', 
                   existing_type=sa.String(32),
                   nullable=True,
                   server_default=None)
    
    # Remove new columns
    op.drop_column('subscription_tier', 'is_billing_exempt')
