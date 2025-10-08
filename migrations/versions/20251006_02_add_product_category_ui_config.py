"""
Add ui_config JSON column to product_category
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20251006_2'
down_revision = '20251006_1'
branch_labels = None
depends_on = None


def table_exists(table_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    if table_exists('product_category') and not column_exists('product_category', 'ui_config'):
        with op.batch_alter_table('product_category') as batch_op:
            batch_op.add_column(sa.Column('ui_config', sa.JSON(), nullable=True))


def downgrade():
    if table_exists('product_category') and column_exists('product_category', 'ui_config'):
        with op.batch_alter_table('product_category') as batch_op:
            batch_op.drop_column('ui_config')
