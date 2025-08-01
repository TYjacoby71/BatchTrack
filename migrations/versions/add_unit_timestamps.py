
"""add missing timestamp columns to unit table

Revision ID: add_unit_timestamps
Revises: fix_nullable_constraints
Create Date: 2025-02-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'add_unit_timestamps'
down_revision = 'fix_nullable_constraints'
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
    """Add missing timestamp columns to unit table"""
    print("=== Adding missing timestamp columns to unit table ===")

    # Add timestamp columns to unit table if they don't exist
    if table_exists('unit'):
        print("Adding timestamp columns to unit table...")
        
        with op.batch_alter_table('unit', schema=None) as batch_op:
            if not column_exists('unit', 'created_at'):
                batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
                print("  ✅ Added created_at column")
            else:
                print("  ℹ️  created_at column already exists")
                
            if not column_exists('unit', 'updated_at'):
                batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
                print("  ✅ Added updated_at column")
            else:
                print("  ℹ️  updated_at column already exists")

    # Add timestamp columns to custom_unit_mapping table if they don't exist
    if table_exists('custom_unit_mapping'):
        print("Adding timestamp columns to custom_unit_mapping table...")
        
        with op.batch_alter_table('custom_unit_mapping', schema=None) as batch_op:
            if not column_exists('custom_unit_mapping', 'created_at'):
                batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
                print("  ✅ Added created_at column")
            else:
                print("  ℹ️  created_at column already exists")
                
            if not column_exists('custom_unit_mapping', 'updated_at'):
                batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
                print("  ✅ Added updated_at column")
            else:
                print("  ℹ️  updated_at column already exists")

    # Add timestamp columns to conversion_log table if they don't exist
    if table_exists('conversion_log'):
        print("Adding timestamp columns to conversion_log table...")
        
        with op.batch_alter_table('conversion_log', schema=None) as batch_op:
            if not column_exists('conversion_log', 'created_at'):
                batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
                print("  ✅ Added created_at column")
            else:
                print("  ℹ️  created_at column already exists")
                
            if not column_exists('conversion_log', 'updated_at'):
                batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
                print("  ✅ Added updated_at column")
            else:
                print("  ℹ️  updated_at column already exists")

    print("✅ Migration completed: Added missing timestamp columns")


def downgrade():
    """Remove timestamp columns"""
    print("=== Removing timestamp columns ===")

    # Remove from conversion_log
    if table_exists('conversion_log'):
        with op.batch_alter_table('conversion_log', schema=None) as batch_op:
            if column_exists('conversion_log', 'updated_at'):
                batch_op.drop_column('updated_at')
            if column_exists('conversion_log', 'created_at'):
                batch_op.drop_column('created_at')

    # Remove from custom_unit_mapping
    if table_exists('custom_unit_mapping'):
        with op.batch_alter_table('custom_unit_mapping', schema=None) as batch_op:
            if column_exists('custom_unit_mapping', 'updated_at'):
                batch_op.drop_column('updated_at')
            if column_exists('custom_unit_mapping', 'created_at'):
                batch_op.drop_column('created_at')

    # Remove from unit
    if table_exists('unit'):
        with op.batch_alter_table('unit', schema=None) as batch_op:
            if column_exists('unit', 'updated_at'):
                batch_op.drop_column('updated_at')
            if column_exists('unit', 'created_at'):
                batch_op.drop_column('created_at')

    print("✅ Downgrade completed")
