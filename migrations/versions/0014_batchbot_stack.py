"""0014 batchbot stack

Revision ID: 0014_batchbot_stack
Revises: 0013_recipe_family
Create Date: 2025-11-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0014_batchbot_stack'
down_revision = '0013_recipe_family'
branch_labels = None
depends_on = None


def upgrade():
    # Usage metering window
    op.create_table(
        'batchbot_usage',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('window_start', sa.Date(), nullable=False),
        sa.Column('window_end', sa.Date(), nullable=False),
        sa.Column('request_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_request_at', sa.DateTime(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('organization_id', 'window_start', name='uq_batchbot_usage_org_window'),
    )
    op.create_index('ix_batchbot_usage_org_id', 'batchbot_usage', ['organization_id'])
    op.create_index('ix_batchbot_usage_user_id', 'batchbot_usage', ['user_id'])
    op.create_index('ix_batchbot_usage_window_start', 'batchbot_usage', ['window_start'])

    # Credit bundles for refills
    op.create_table(
        'batchbot_credit_bundle',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=False),
        sa.Column('addon_id', sa.Integer(), sa.ForeignKey('addon.id'), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=False, server_default='manual'),
        sa.Column('reference', sa.String(length=128), nullable=True),
        sa.Column('purchased_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('remaining_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_batchbot_credit_bundle_org_id', 'batchbot_credit_bundle', ['organization_id'])
    op.create_index('ix_batchbot_credit_bundle_addon_id', 'batchbot_credit_bundle', ['addon_id'])

    # Addon knob for bundled credits
    op.add_column('addon', sa.Column('batchbot_credit_amount', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    from migrations.postgres_helpers import safe_drop_column, safe_drop_index, table_exists
    
    # Drop batchbot_credit_amount column from addon table
    safe_drop_column('addon', 'batchbot_credit_amount')

    # Drop batchbot_credit_bundle table and indexes
    safe_drop_index('ix_batchbot_credit_bundle_addon_id', 'batchbot_credit_bundle')
    safe_drop_index('ix_batchbot_credit_bundle_org_id', 'batchbot_credit_bundle')
    if table_exists('batchbot_credit_bundle'):
        op.drop_table('batchbot_credit_bundle')

    # Drop batchbot_usage table and indexes
    safe_drop_index('ix_batchbot_usage_window_start', 'batchbot_usage')
    safe_drop_index('ix_batchbot_usage_user_id', 'batchbot_usage')
    safe_drop_index('ix_batchbot_usage_org_id', 'batchbot_usage')
    if table_exists('batchbot_usage'):
        op.drop_table('batchbot_usage')