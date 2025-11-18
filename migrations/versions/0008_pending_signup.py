"""0008 pending signup support

Revision ID: 0008_pending_signup
Revises: 0007_single_sesh_enfor
Create Date: 2025-11-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import table_exists


# revision identifiers, used by Alembic.
revision = '0008_pending_signup'
down_revision = '0007_single_sesh_enfor'
branch_labels = None
depends_on = None


def upgrade():
    if table_exists('pending_signup'):
        return

    op.create_table(
        'pending_signup',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('signup_source', sa.String(length=64), nullable=True),
        sa.Column('referral_code', sa.String(length=64), nullable=True),
        sa.Column('promo_code', sa.String(length=64), nullable=True),
        sa.Column('detected_timezone', sa.String(length=64), nullable=True),
        sa.Column('tier_id', sa.Integer(), sa.ForeignKey('subscription_tier.id'), nullable=False),
        sa.Column('oauth_provider', sa.String(length=64), nullable=True),
        sa.Column('oauth_provider_id', sa.String(length=255), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('client_reference_id', sa.String(length=255), nullable=True, unique=True),
        sa.Column('stripe_checkout_session_id', sa.String(length=255), nullable=True, unique=True),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )

    op.create_index('ix_pending_signup_email', 'pending_signup', ['email'])
    op.create_index('ix_pending_signup_status', 'pending_signup', ['status'])
    op.create_index('ix_pending_signup_tier_id', 'pending_signup', ['tier_id'])
    op.create_index('ix_pending_signup_stripe_customer_id', 'pending_signup', ['stripe_customer_id'])


def downgrade():
    if not table_exists('pending_signup'):
        return
    op.drop_index('ix_pending_signup_stripe_customer_id', table_name='pending_signup')
    op.drop_index('ix_pending_signup_tier_id', table_name='pending_signup')
    op.drop_index('ix_pending_signup_status', table_name='pending_signup')
    op.drop_index('ix_pending_signup_email', table_name='pending_signup')
    op.drop_table('pending_signup')
