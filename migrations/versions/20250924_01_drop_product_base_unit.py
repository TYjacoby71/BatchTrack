"""
Drop Product.base_unit column

Revision ID: 20250924_01
Revises: 20250923_04
Create Date: 2025-09-24
"""

from alembic import op
import sqlalchemy as sa

revision = '20250924_01'
down_revision = '20250923_04'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c['name'] for c in inspector.get_columns(table_name)]
    return column_name in cols


def upgrade():
    if column_exists('product', 'base_unit'):
        with op.batch_alter_table('product') as batch_op:
            batch_op.drop_column('base_unit')


def downgrade():
    # Best-effort restore; default to 'g' to match previous default
    if not column_exists('product', 'base_unit'):
        with op.batch_alter_table('product') as batch_op:
            batch_op.add_column(sa.Column('base_unit', sa.String(length=32), nullable=True))
