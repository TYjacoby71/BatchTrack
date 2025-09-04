"""
Extend GlobalItem with synonyms and perishable defaults

Revision ID: 20250904_02
Revises: 20250904_01
Create Date: 2025-09-04
"""

from alembic import op
import sqlalchemy as sa

revision = '20250904_02'
down_revision = '20250904_01a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('global_item') as batch_op:
        batch_op.add_column(sa.Column('default_is_perishable', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('recommended_shelf_life_days', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('aka_names', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('global_item') as batch_op:
        try:
            batch_op.drop_column('aka_names')
        except Exception:
            pass
        try:
            batch_op.drop_column('recommended_shelf_life_days')
        except Exception:
            pass
        try:
            batch_op.drop_column('default_is_perishable')
        except Exception:
            pass

