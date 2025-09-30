
"""Add soap making and cosmetic formulation attributes to inventory items

Revision ID: 20250930_2
Revises: 20250930_1
Create Date: 2025-09-30 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20250930_2'
down_revision = '20250930_1'
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
    """Add soap making and cosmetic formulation attributes to inventory_item table"""
    print("=== Adding soap making and cosmetic formulation fields to inventory items ===")
    
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
    
    # Check inventory_item table
    if table_exists('inventory_item'):
        print("Processing inventory_item table...")
        
        with op.batch_alter_table('inventory_item') as batch_op:
            # Add all soap making and cosmetic formulation fields
            for field_name, field_type in soap_making_fields:
                if not column_exists('inventory_item', field_name):
                    batch_op.add_column(sa.Column(field_name, field_type, nullable=True))
                    print(f"  ✅ Added {field_name} to inventory_item")
                else:
                    print(f"  ℹ️  {field_name} already exists in inventory_item")
    else:
        print("  ⚠️  inventory_item table does not exist")

    print("✅ Soap making and cosmetic formulation fields migration completed successfully")


def downgrade():
    """Remove soap making and cosmetic formulation attributes from inventory_item table"""
    print("=== Removing soap making and cosmetic formulation fields from inventory items ===")
    
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
    
    # Remove from inventory_item
    if table_exists('inventory_item'):
        print("Removing soap making fields from inventory_item...")
        try:
            with op.batch_alter_table('inventory_item') as batch_op:
                for field_name in soap_making_fields:
                    if column_exists('inventory_item', field_name):
                        batch_op.drop_column(field_name)
                        print(f"  ✅ Removed {field_name} from inventory_item")
        except Exception as e:
            print(f"  ⚠️  Error removing columns from inventory_item: {e}")

    print("✅ Soap making and cosmetic formulation fields downgrade completed")
