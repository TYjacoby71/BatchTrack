
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
    
    # For SQLite compatibility, use batch_alter_table for column modifications
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        # Update billing_provider to be non-nullable with default
        batch_op.alter_column('billing_provider', 
                             existing_type=sa.String(32),
                             nullable=False,
                             server_default='exempt')
    
    # Remove deprecated columns if they exist
    try:
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.drop_column('is_available')
    except:
        pass  # Column may not exist
        
    try:
        with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
            batch_op.drop_column('tier_type')
    except:
        pass  # Column may not exist

def downgrade():
    # Add back deprecated columns
    op.add_column('subscription_tier', sa.Column('is_available', sa.Boolean(), default=True))
    op.add_column('subscription_tier', sa.Column('tier_type', sa.String(32), default='paid'))
    
    # Make billing_provider nullable again
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        batch_op.alter_column('billing_provider', 
                             existing_type=sa.String(32),
                             nullable=True,
                             server_default=None)
    
    # Remove new columns
    with op.batch_alter_table('subscription_tier', schema=None) as batch_op:
        batch_op.drop_column('is_billing_exempt')
