"""0011 batchbot usage metering

Revision ID: 0011_batchbot_usage
Revises: 0010_recipe_status_drafts
Create Date: 2025-11-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0011_batchbot_usage'
down_revision = '0010_recipe_status_drafts'
branch_labels = None
depends_on = None


def upgrade():
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


def downgrade():
    op.drop_index('ix_batchbot_usage_window_start', table_name='batchbot_usage')
    op.drop_index('ix_batchbot_usage_user_id', table_name='batchbot_usage')
    op.drop_index('ix_batchbot_usage_org_id', table_name='batchbot_usage')
    op.drop_table('batchbot_usage')
