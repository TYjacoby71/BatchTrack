
"""Add soap making and cosmetic formulation attributes to global_item table

Revision ID: 20250930_3
Revises: 20250930_2
Create Date: 2025-09-30 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20250930_3'
down_revision = '20250930_2'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    """Add soap making and cosmetic formulation attributes to global_item table"""
    print("=== Adding soap making and cosmetic formulation fields to global_item ===")
    
    # Define all the soap making and cosmetic formulation fields
    soap_making_fields = [
        ('saponification_value', sa.Float()),
        ('iodine_value', sa.Float()),
        ('melting_point_c', sa.Float()),
        ('flash_point_c', sa.Float()),
        ('ph_value', sa.Float()),
        ('moisture_content_percent', sa.Float()),
        ('shelf_life_months', sa.Integer()),
        ('comedogenic_rating', sa.Integer())
    ]
    
    # Check global_item table
    if table_exists('global_item'):
        print("Processing global_item table...")
        
        with op.batch_alter_table('global_item') as batch_op:
            # Add all soap making and cosmetic formulation fields
            for field_name, field_type in soap_making_fields:
                if not column_exists('global_item', field_name):
                    batch_op.add_column(sa.Column(field_name, field_type, nullable=True))
                    print(f"  ✅ Added {field_name} to global_item")
                else:
                    print(f"  ℹ️  {field_name} already exists in global_item")
    else:
        print("  ⚠️  global_item table does not exist")

    print("✅ Soap making and cosmetic formulation fields migration for global_item completed successfully")


def downgrade():
    """Remove soap making and cosmetic formulation attributes from global_item table"""
    print("=== Removing soap making and cosmetic formulation fields from global_item ===")
    
    soap_making_fields = [
        'comedogenic_rating',
        'shelf_life_months', 
        'moisture_content_percent',
        'ph_value',
        'flash_point_c',
        'melting_point_c',
        'iodine_value',
        'saponification_value'
    ]
    
    # Remove from global_item
    if table_exists('global_item'):
        print("Removing soap making fields from global_item...")
        try:
            with op.batch_alter_table('global_item') as batch_op:
                for field_name in soap_making_fields:
                    if column_exists('global_item', field_name):
                        batch_op.drop_column(field_name)
                        print(f"  ✅ Removed {field_name} from global_item")
        except Exception as e:
            print(f"  ⚠️  Error removing columns from global_item: {e}")

    print("✅ Soap making and cosmetic formulation fields downgrade for global_item completed")
