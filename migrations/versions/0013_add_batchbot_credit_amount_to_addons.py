"""0013 add batchbot credit amount to addons

Revision ID: 0013_add_batchbot_credit_amount_to_addons
Revises: 0012_batchbot_credit_bundles
Create Date: 2025-11-24 00:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0013_add_batchbot_credit_amount_to_addons'
down_revision = '0012_batchbot_credit_bundles'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('addon', sa.Column('batchbot_credit_amount', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('addon', 'batchbot_credit_amount')
