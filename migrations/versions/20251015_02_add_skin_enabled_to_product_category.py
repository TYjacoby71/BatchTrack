"""
Add skin_enabled boolean to product_category
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20251015_02'
down_revision = '20251015_01'
branch_labels = None
depends_on = None

def table_exists(table_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    return column_name in [c['name'] for c in inspector.get_columns(table_name)]

def upgrade():
    if table_exists('product_category') and not column_exists('product_category', 'skin_enabled'):
        with op.batch_alter_table('product_category') as batch_op:
            batch_op.add_column(sa.Column('skin_enabled', sa.Boolean(), nullable=True))
        try:
            op.execute("UPDATE product_category SET skin_enabled = FALSE WHERE skin_enabled IS NULL")
        except Exception:
            pass

def downgrade():
    if table_exists('product_category') and column_exists('product_category', 'skin_enabled'):
        with op.batch_alter_table('product_category') as batch_op:
            batch_op.drop_column('skin_enabled')
