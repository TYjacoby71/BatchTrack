"""0015 batch label org scope

Revision ID: 0015_batch_label_org_scope
Revises: 0014_batchbot_stack
Create Date: 2025-11-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0015_batch_label_org_scope'
down_revision = '0014_batchbot_stack'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('batch_label_code_key', 'batch', type_='unique')
    op.create_unique_constraint('uq_batch_org_label', 'batch', ['organization_id', 'label_code'])


def downgrade():
    op.drop_constraint('uq_batch_org_label', 'batch', type_='unique')
    op.create_unique_constraint('batch_label_code_key', 'batch', ['label_code'])
