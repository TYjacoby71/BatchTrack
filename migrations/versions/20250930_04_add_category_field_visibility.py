
"""Add visibility control fields for soap-making attributes to ingredient categories

Revision ID: 20250930_04
Revises: 20250930_03
Create Date: 2025-09-30 04:00:00

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
        print(f"  ✅ Added column {column.name} to {table_name}")
    else:
        print(f"  ℹ️  Column {column.name} already exists in {table_name}")


def safe_drop_column(table_name, column_name):
    """Drop column if it exists"""
    connection = op.get_bind()
    inspector = inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
    
    if column_name in existing_columns:
        op.drop_column(table_name, column_name)
        print(f"  ✅ Dropped column {column_name} from {table_name}")
    else:
        print(f"  ℹ️  Column {column_name} does not exist in {table_name}")


# revision identifiers, used by Alembic.
revision = '20250930_04'
down_revision = '20250930_03'
branch_labels = None
depends_on = None


def upgrade():
    """Add visibility control fields to ingredient categories"""
    print("=== Adding visibility control fields to ingredient_category ===")
    
    # Add visibility control fields for soap-making attributes
    safe_add_column('ingredient_category', sa.Column('show_saponification_value', sa.Boolean(), nullable=True, default=False))
    safe_add_column('ingredient_category', sa.Column('show_iodine_value', sa.Boolean(), nullable=True, default=False))
    safe_add_column('ingredient_category', sa.Column('show_melting_point_c', sa.Boolean(), nullable=True, default=False))
    safe_add_column('ingredient_category', sa.Column('show_flash_point_c', sa.Boolean(), nullable=True, default=False))
    safe_add_column('ingredient_category', sa.Column('show_ph_value', sa.Boolean(), nullable=True, default=False))
    safe_add_column('ingredient_category', sa.Column('show_moisture_content_percent', sa.Boolean(), nullable=True, default=False))
    safe_add_column('ingredient_category', sa.Column('show_shelf_life_months', sa.Boolean(), nullable=True, default=False))
    safe_add_column('ingredient_category', sa.Column('show_comedogenic_rating', sa.Boolean(), nullable=True, default=False))
    
    print("✅ Visibility control fields migration completed")


def downgrade():
    """Remove visibility control fields"""
    print("=== Removing visibility control fields from ingredient_category ===")
    
    safe_drop_column('ingredient_category', 'show_comedogenic_rating')
    safe_drop_column('ingredient_category', 'show_shelf_life_months')
    safe_drop_column('ingredient_category', 'show_moisture_content_percent')
    safe_drop_column('ingredient_category', 'show_ph_value')
    safe_drop_column('ingredient_category', 'show_flash_point_c')
    safe_drop_column('ingredient_category', 'show_melting_point_c')
    safe_drop_column('ingredient_category', 'show_iodine_value')
    safe_drop_column('ingredient_category', 'show_saponification_value')
    
    print("✅ Visibility control fields removal completed")
