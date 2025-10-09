"""
Add portion columns to recipe and batch: is_portioned, portion_name, counts

Revision ID: 20250925_01
Revises: 20250924_01
Create Date: 2025-09-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


def safe_add_column(table_name, column):
    """Add column if it doesn't already exist"""
    connection = op.get_bind()
    inspector = inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
    
    if column.name not in existing_columns:
        op.add_column(table_name, column)
        print(f"Added column {column.name} to {table_name}")
    else:
        print(f"Column {column.name} already exists in {table_name}, skipping")


def safe_drop_column(table_name, column_name):
    """Drop column if it exists"""
    connection = op.get_bind()
    inspector = inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
    
    if column_name in existing_columns:
        op.drop_column(table_name, column_name)
        print(f"Dropped column {column_name} from {table_name}")
    else:
        print(f"Column {column_name} does not exist in {table_name}, skipping")


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