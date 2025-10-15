"""
Make product_category.organization_id nullable to support global categories

Revision ID: 20251015_01
Revises: 20251009_3
Create Date: 2025-10-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '20251015_01'
down_revision = '20251009_3'
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    if not _table_exists(bind, table_name):
        return False
    inspector = inspect(bind)
    return column_name in [col['name'] for col in inspector.get_columns(table_name)]


def _is_not_null(bind, table_name: str, column_name: str) -> bool:
    inspector = inspect(bind)
    for col in inspector.get_columns(table_name):
        if col['name'] == column_name:
            # SQLAlchemy reports nullable (True means NULL is allowed)
            return not col.get('nullable', True)
    return False


def upgrade():
    bind = op.get_bind()

    if not _table_exists(bind, 'product_category'):
        return

    if not _column_exists(bind, 'product_category', 'organization_id'):
        # Column no longer exists; nothing to change
        return

    # Only alter if it's currently NOT NULL
    if _is_not_null(bind, 'product_category', 'organization_id'):
        with op.batch_alter_table('product_category') as batch_op:
            batch_op.alter_column(
                'organization_id',
                existing_type=sa.Integer(),
                nullable=True
            )


def downgrade():
    # Downgrade re-applies NOT NULL if the column exists
    bind = op.get_bind()

    if not _table_exists(bind, 'product_category'):
        return

    if not _column_exists(bind, 'product_category', 'organization_id'):
        return

    with op.batch_alter_table('product_category') as batch_op:
        batch_op.alter_column(
            'organization_id',
            existing_type=sa.Integer(),
            nullable=False
        )
