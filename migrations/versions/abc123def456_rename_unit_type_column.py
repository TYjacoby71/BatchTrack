
"""rename unit type column to unit_type

Revision ID: abc123def456
Revises: 132971c1d456
Create Date: 2025-08-01 19:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'abc123def456'
down_revision = '132971c1d456'
branch_labels = ('unit_type_rename',)
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
    """Rename unit.type column to unit.unit_type"""
    
    if table_exists('unit'):
        # Check if we need to rename the column
        if column_exists('unit', 'type') and not column_exists('unit', 'unit_type'):
            print("Renaming unit.type to unit.unit_type...")
            
            # For SQLite, we need to recreate the table since it doesn't support column renaming in older versions
            bind = op.get_bind()
            if 'sqlite' in str(bind.engine.url):
                # SQLite approach: recreate table with new column name
                with op.batch_alter_table('unit', schema=None) as batch_op:
                    batch_op.alter_column('type', new_column_name='unit_type')
                    
                print("✅ Renamed unit.type to unit.unit_type (SQLite)")
            else:
                # PostgreSQL approach: direct column rename
                op.alter_column('unit', 'type', new_column_name='unit_type')
                print("✅ Renamed unit.type to unit.unit_type (PostgreSQL)")
        
        elif column_exists('unit', 'unit_type'):
            print("Column unit.unit_type already exists - no changes needed")
        else:
            print("Warning: Neither type nor unit_type column found in unit table")
    else:
        print("Unit table does not exist")


def downgrade():
    """Rename unit.unit_type column back to unit.type"""
    
    if table_exists('unit'):
        # Check if we need to rename the column back
        if column_exists('unit', 'unit_type') and not column_exists('unit', 'type'):
            print("Renaming unit.unit_type back to unit.type...")
            
            bind = op.get_bind()
            if 'sqlite' in str(bind.engine.url):
                # SQLite approach: recreate table with old column name
                with op.batch_alter_table('unit', schema=None) as batch_op:
                    batch_op.alter_column('unit_type', new_column_name='type')
                    
                print("✅ Renamed unit.unit_type back to unit.type (SQLite)")
            else:
                # PostgreSQL approach: direct column rename
                op.alter_column('unit', 'unit_type', new_column_name='type')
                print("✅ Renamed unit.unit_type back to unit.type (PostgreSQL)")
        
        elif column_exists('unit', 'type'):
            print("Column unit.type already exists - no changes needed")
        else:
            print("Warning: Neither unit_type nor type column found in unit table")
    else:
        print("Unit table does not exist")
