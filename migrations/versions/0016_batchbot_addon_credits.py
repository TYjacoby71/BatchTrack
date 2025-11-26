"""0016 batchbot addon credits

Revision ID: 0016_batchbot_addon_credits
Revises: 0015_batchbot_credit_bundles
Create Date: 2025-11-24 00:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0016_batchbot_addon_credits'
down_revision = '0015_batchbot_credit_bundles'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('addon', sa.Column('batchbot_credit_amount', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('addon', 'batchbot_credit_amount')
