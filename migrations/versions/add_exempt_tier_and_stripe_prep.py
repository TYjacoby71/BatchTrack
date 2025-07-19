
"""Add exempt tier and prepare for Stripe integration

Revision ID: add_exempt_tier_and_stripe_prep
Revises: final_head_merge_2025
Create Date: 2025-01-19 05:00:00

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'add_exempt_tier_and_stripe_prep'
down_revision = 'final_head_merge_2025'
branch_labels = None
depends_on = None

def upgrade():
    # Add missing columns to organization table if they don't exist
    try:
        with op.batch_alter_table('organization', schema=None) as batch_op:
            batch_op.add_column(sa.Column('signup_source', sa.String(64), nullable=True))
            batch_op.add_column(sa.Column('promo_code', sa.String(32), nullable=True))
            batch_op.add_column(sa.Column('referral_code', sa.String(32), nullable=True))
    except Exception as e:
        print(f"Columns may already exist: {e}")
    
    # Add trial_tier column to subscription table if it doesn't exist
    try:
        with op.batch_alter_table('subscription', schema=None) as batch_op:
            batch_op.add_column(sa.Column('trial_tier', sa.String(32), nullable=True))
    except Exception as e:
        print(f"Column may already exist: {e}")
    
    # Create subscription for organization 1 if it doesn't exist
    connection = op.get_bind()
    
    # Check if organization 1 exists and has no subscription
    org_result = connection.execute(sa.text("SELECT id FROM organization WHERE id = 1")).fetchone()
    if org_result:
        sub_result = connection.execute(sa.text("SELECT id FROM subscription WHERE organization_id = 1")).fetchone()
        if not sub_result:
            # Create exempt subscription for organization 1
            connection.execute(sa.text("""
                INSERT INTO subscription (organization_id, tier, status, created_at, updated_at, notes)
                VALUES (1, 'exempt', 'active', :now, :now, 'Reserved organization for owner and testing')
            """), {"now": datetime.utcnow()})
            print("Created exempt subscription for organization 1")

def downgrade():
    # Remove trial_tier column
    try:
        with op.batch_alter_table('subscription', schema=None) as batch_op:
            batch_op.drop_column('trial_tier')
    except Exception:
        pass
    
    # Remove organization columns
    try:
        with op.batch_alter_table('organization', schema=None) as batch_op:
            batch_op.drop_column('signup_source')
            batch_op.drop_column('promo_code')
            batch_op.drop_column('referral_code')
    except Exception:
        pass
