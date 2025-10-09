"""
Add portioning_data JSON to recipe and batch

Revision ID: 20250923_03
Revises: 20250923_02
Create Date: 2025-09-23
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250923_03'
down_revision = '20250923_02'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)

    def column_exists(table_name, column_name):
        """Check if a column exists in a table"""
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception:
            return False

    # Add portioning_data JSON column to recipe table if it doesn't exist
    if not column_exists('recipe', 'portioning_data'):
        with op.batch_alter_table('recipe') as batch_op:
            batch_op.add_column(sa.Column('portioning_data', sa.JSON(), nullable=True))
        print("Added portioning_data column to recipe table")
    else:
        print("portioning_data column already exists in recipe table")

    # Add portioning_data JSON column to batch table if it doesn't exist
    if not column_exists('batch', 'portioning_data'):
        with op.batch_alter_table('batch') as batch_op:
            batch_op.add_column(sa.Column('portioning_data', sa.JSON(), nullable=True))
        print("Added portioning_data column to batch table")
    else:
        print("portioning_data column already exists in batch table")


def downgrade():
    try:
        with op.batch_alter_table('batch') as batch_op:
            batch_op.drop_column('portioning_data')
    except Exception:
        pass

    try:
        with op.batch_alter_table('recipe') as batch_op:
            batch_op.drop_column('portioning_data')
    except Exception:
        pass