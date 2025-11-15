"""0007 single session enforcement

Revision ID: 0007_single_session_enforcement
Revises: 0006_recipe_lineage_upgrade
Create Date: 2025-11-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import (
    is_sqlite,
    safe_drop_column,
    table_exists,
)


# revision identifiers, used by Alembic.
revision = '0007_single_session_enforcement'
down_revision = '0006_recipe_lineage_upgrade'
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists('user'):
        return
    column = sa.Column('active_session_token', sa.String(length=255), nullable=True)
    if is_sqlite():
        with op.batch_alter_table('user', recreate='always') as batch_op:
            batch_op.add_column(column)
    else:
        op.add_column('user', column)


def downgrade():
    if not table_exists('user'):
        return

    safe_drop_column('user', 'active_session_token')
