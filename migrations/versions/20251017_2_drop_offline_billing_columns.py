"""drop offline billing snapshot columns

Revision ID: 20251017_2
Revises: 20251017_1
Create Date: 2025-10-17 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20251017_2'
down_revision = '20251017_1'
branch_labels = None
depends_on = None


def _column_exists(conn, table: str, column: str) -> bool:
    try:
        insp = inspect(conn)
        return column in [c['name'] for c in insp.get_columns(table)]
    except Exception:
        return False


def upgrade():
    conn = op.get_bind()
    table = 'organization'
    for col in ['offline_tier_cache', 'last_online_sync']:
        if _column_exists(conn, table, col):
            try:
                with op.batch_alter_table(table) as batch_op:
                    batch_op.drop_column(col)
            except Exception:
                # Some backends may not support batch; try direct
                try:
                    op.execute(sa.text(f'ALTER TABLE {table} DROP COLUMN IF EXISTS {col}'))
                except Exception:
                    pass


def downgrade():
    conn = op.get_bind()
    table = 'organization'
    # Best-effort restore with nullable types
    if not _column_exists(conn, table, 'last_online_sync'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('last_online_sync', sa.DateTime(), nullable=True))
    if not _column_exists(conn, table, 'offline_tier_cache'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('offline_tier_cache', sa.JSON(), nullable=True))
