"""
Add category_data JSON column to recipe table

Revision ID:
20251006_1
Revises:
20251001_2
Create Date: 2025-10-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20251006_1'
down_revision = '20251001_2'
branch_labels = None
depends_on = None


def table_exists(table_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


essential_columns = ['id']

def column_exists(table_name, column_name):
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    if table_exists('recipe') and not column_exists('recipe', 'category_data'):
        with op.batch_alter_table('recipe') as batch_op:
            batch_op.add_column(sa.Column('category_data', sa.JSON(), nullable=True))


def downgrade():
    if table_exists('recipe') and column_exists('recipe', 'category_data'):
        with op.batch_alter_table('recipe') as batch_op:
            batch_op.drop_column('category_data')
