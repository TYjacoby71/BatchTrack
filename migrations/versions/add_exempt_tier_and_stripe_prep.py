
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
    # Get current table info to check existing columns
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Check organization table columns
    org_columns = [col['name'] for col in inspector.get_columns('organization')]
    
    # Add missing columns to organization table
    with op.batch_alter_table('organization', schema=None) as batch_op:
        if 'signup_source' not in org_columns:
            batch_op.add_column(sa.Column('signup_source', sa.String(64), nullable=True))
            print("Added signup_source column")
        if 'promo_code' not in org_columns:
            batch_op.add_column(sa.Column('promo_code', sa.String(32), nullable=True))
            print("Added promo_code column")
        if 'referral_code' not in org_columns:
            batch_op.add_column(sa.Column('referral_code', sa.String(32), nullable=True))
            print("Added referral_code column")
    
    # Check subscription table exists and add trial_tier column
    tables = inspector.get_table_names()
    if 'subscription' in tables:
        sub_columns = [col['name'] for col in inspector.get_columns('subscription')]
        if 'trial_tier' not in sub_columns:
            with op.batch_alter_table('subscription', schema=None) as batch_op:
                batch_op.add_column(sa.Column('trial_tier', sa.String(32), nullable=True))
                print("Added trial_tier column to subscription")
    
        # Create subscription for organization 1 if it doesn't exist
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
