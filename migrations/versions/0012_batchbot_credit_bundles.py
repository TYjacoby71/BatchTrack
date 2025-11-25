"""0012 batchbot credit bundles

Revision ID: 0012_batchbot_credit_bundles
Revises: 0011_batchbot_usage
Create Date: 2025-11-24 00:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0012_batchbot_credit_bundles'
down_revision = '0011_batchbot_usage'
branch_labels = None
depends_on = None


def upgrade():
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


def downgrade():
    op.drop_index('ix_batchbot_credit_bundle_addon_id', table_name='batchbot_credit_bundle')
    op.drop_index('ix_batchbot_credit_bundle_org_id', table_name='batchbot_credit_bundle')
    op.drop_table('batchbot_credit_bundle')
