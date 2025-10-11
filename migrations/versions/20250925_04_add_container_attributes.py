
"""Add container structured attributes to inventory_item and global_item

Revision ID: 20250925_04
Revises: 20250925_03
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
revision = '20250925_04'
down_revision = '20250925_03'
branch_labels = None
depends_on = None


def upgrade():
    # Add container attributes to inventory_item table using safe operations
    safe_add_column('inventory_item', sa.Column('container_material', sa.String(64), nullable=True))
    safe_add_column('inventory_item', sa.Column('container_volume', sa.Float(), nullable=True))
    safe_add_column('inventory_item', sa.Column('container_volume_unit', sa.String(16), nullable=True))
    safe_add_column('inventory_item', sa.Column('container_dimensions', sa.String(128), nullable=True))
    safe_add_column('inventory_item', sa.Column('container_color', sa.String(32), nullable=True))
    safe_add_column('inventory_item', sa.Column('container_closure_type', sa.String(32), nullable=True))
    safe_add_column('inventory_item', sa.Column('container_shape', sa.String(32), nullable=True))
    safe_add_column('inventory_item', sa.Column('container_style', sa.String(64), nullable=True))

    # Add container attributes to global_item table using safe operations
    safe_add_column('global_item', sa.Column('container_material', sa.String(64), nullable=True))
    safe_add_column('global_item', sa.Column('container_volume', sa.Float(), nullable=True))
    safe_add_column('global_item', sa.Column('container_volume_unit', sa.String(16), nullable=True))
    safe_add_column('global_item', sa.Column('container_dimensions', sa.String(128), nullable=True))
    safe_add_column('global_item', sa.Column('container_color', sa.String(32), nullable=True))
    safe_add_column('global_item', sa.Column('container_closure_type', sa.String(32), nullable=True))
    safe_add_column('global_item', sa.Column('container_shape', sa.String(32), nullable=True))
    safe_add_column('global_item', sa.Column('container_style', sa.String(64), nullable=True))


def downgrade():
    # Remove container attributes from both tables using safe operations
    safe_drop_column('inventory_item', 'container_style')
    safe_drop_column('inventory_item', 'container_shape')
    safe_drop_column('inventory_item', 'container_closure_type')
    safe_drop_column('inventory_item', 'container_color')
    safe_drop_column('inventory_item', 'container_dimensions')
    safe_drop_column('inventory_item', 'container_volume_unit')
    safe_drop_column('inventory_item', 'container_volume')
    safe_drop_column('inventory_item', 'container_material')

    safe_drop_column('global_item', 'container_style')
    safe_drop_column('global_item', 'container_shape')
    safe_drop_column('global_item', 'container_closure_type')
    safe_drop_column('global_item', 'container_color')
    safe_drop_column('global_item', 'container_dimensions')
    safe_drop_column('global_item', 'container_volume_unit')
    safe_drop_column('global_item', 'container_volume')
    safe_drop_column('global_item', 'container_material')
