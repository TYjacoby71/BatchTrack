"""
Add portion columns to recipe and batch: is_portioned, portion_name, counts

Revision ID: 20250925_01
Revises: 20250924_01
Create Date: 2025-09-25
"""

from alembic import op
import sqlalchemy as sa

# Import postgres_helpers if it exists and is needed for safe operations
try:
    from backend.utils.postgres_helpers import safe_add_column, safe_drop_column
except ImportError:
    # Define dummy functions if postgres_helpers is not available
    def safe_add_column(table_name, column):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(column)

    def safe_drop_column(table_name, column_name):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column(column_name)


# revision identifiers, used by Alembic.
revision = '20250925_01'
down_revision = '20250924_01'
branch_labels = None
depends_on = None


def upgrade():
    # Add portion columns to recipe table using safe operations
    safe_add_column('recipe', sa.Column('is_portioned', sa.Boolean(), nullable=True))
    safe_add_column('recipe', sa.Column('portion_name', sa.String(100), nullable=True))
    safe_add_column('recipe', sa.Column('counts', sa.Integer(), nullable=True))

    # Add portion columns to batch table using safe operations
    safe_add_column('batch', sa.Column('is_portioned', sa.Boolean(), nullable=True))
    safe_add_column('batch', sa.Column('portion_name', sa.String(100), nullable=True))
    safe_add_column('batch', sa.Column('counts', sa.Integer(), nullable=True))


def downgrade():
    # Remove portion columns from batch table using safe operations
    safe_drop_column('batch', 'counts')
    safe_drop_column('batch', 'portion_name')
    safe_drop_column('batch', 'is_portioned')

    # Remove portion columns from recipe table using safe operations
    safe_drop_column('recipe', 'counts')
    safe_drop_column('recipe', 'portion_name')
    safe_drop_column('recipe', 'is_portioned')