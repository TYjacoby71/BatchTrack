
"""Add plan_snapshot JSON to batch

Revision ID: 20250925_02
Revises: 20250925_01
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
revision = '20250925_02'
down_revision = '20250925_01'
branch_labels = None
depends_on = None


def upgrade():
    # Add plan_snapshot column to batch table using safe operation
    safe_add_column('batch', sa.Column('plan_snapshot', sa.JSON(), nullable=True))


def downgrade():
    # Remove plan_snapshot column from batch table using safe operation
    safe_drop_column('batch', 'plan_snapshot')
