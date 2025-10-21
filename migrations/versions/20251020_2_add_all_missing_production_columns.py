
"""Add all missing production columns that exist in models but not in database

Revision ID: 20251020_2
Revises: 20251020_1
Create Date: 2025-10-20 00:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect

# revision identifiers, used by Alembic.
revision = '20251020_2'
down_revision = '20251020_1'
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    inspector = inspect(op.get_bind())
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def table_exists(table_name):
    """Check if a table exists"""
    inspector = inspect(op.get_bind())
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False

def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key constraint exists"""
    if not table_exists(table_name):
        return False
    inspector = inspect(op.get_bind())
    try:
        fks = inspector.get_foreign_keys(table_name)
        return any(fk.get('name') == fk_name for fk in fks)
    except Exception:
        return False

def safe_add_column(table_name, column_name, column_def):
    """Safely add a column only if it doesn't exist"""
    if not table_exists(table_name):
        print(f"   ⚠️  Table {table_name} does not exist - skipping {column_name}")
        return False
    
    if column_exists(table_name, column_name):
        print(f"   ✅ {column_name} already exists in {table_name}")
        return False
    
    try:
        op.add_column(table_name, column_def)
        print(f"   ✅ Added {column_name} to {table_name}")
        return True
    except Exception as e:
        print(f"   ❌ Failed to add {column_name} to {table_name}: {e}")
        raise

def safe_create_foreign_key(constraint_name, source_table, referent_table, local_cols, remote_cols, **kwargs):
    """Safely create a foreign key constraint"""
    if foreign_key_exists(source_table, constraint_name):
        print(f"   ✅ Foreign key {constraint_name} already exists")
        return False
    
    try:
        # Use batch mode for SQLite compatibility
        with op.batch_alter_table(source_table, schema=None) as batch_op:
            batch_op.create_foreign_key(constraint_name, referent_table, local_cols, remote_cols, **kwargs)
        print(f"   ✅ Created foreign key {constraint_name}")
        return True
    except Exception as e:
        print(f"   ⚠️  Could not create foreign key {constraint_name}: {e}")
        return False  # Don't raise, just warn

def upgrade():
    """Add all missing columns that exist in models but not in database schema"""
    print("=== Adding All Missing Production Columns ===")
    
    # Fix developer_permission.category - missing column
    if table_exists('developer_permission'):
        safe_add_column('developer_permission', 'category', 
                       sa.Column('category', sa.String(length=64), nullable=True))
    
    # Fix unit.is_active - missing column
    if table_exists('unit'):
        safe_add_column('unit', 'is_active', 
                       sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    
    # Fix role.is_active - missing column  
    if table_exists('role'):
        safe_add_column('role', 'is_active', 
                       sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    
    # Fix ingredient_category.description - missing column
    if table_exists('ingredient_category'):
        safe_add_column('ingredient_category', 'description', 
                       sa.Column('description', sa.Text(), nullable=True))
    
    # Add any other missing columns that might be needed for production
    
    # Fix developer_permission missing columns if they exist in model
    if table_exists('developer_permission'):
        safe_add_column('developer_permission', 'is_active', 
                       sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    
    # Fix any missing timestamp columns
    if table_exists('unit'):
        safe_add_column('unit', 'created_at', 
                       sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')))
        safe_add_column('unit', 'updated_at', 
                       sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')))
    
    if table_exists('role'):
        safe_add_column('role', 'created_at', 
                       sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')))
        safe_add_column('role', 'created_by', 
                       sa.Column('created_by', sa.Integer(), nullable=True))
        safe_add_column('role', 'organization_id', 
                       sa.Column('organization_id', sa.Integer(), nullable=True))
        safe_add_column('role', 'is_system_role', 
                       sa.Column('is_system_role', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    
    # Add foreign key constraints safely
    if table_exists('role') and table_exists('user') and column_exists('role', 'created_by'):
        safe_create_foreign_key('fk_role_created_by_user', 'role', 'user', ['created_by'], ['id'])
    
    if table_exists('role') and table_exists('organization') and column_exists('role', 'organization_id'):
        safe_create_foreign_key('fk_role_organization', 'role', 'organization', ['organization_id'], ['id'])
    
    # Fix unit foreign key constraints
    if table_exists('unit') and table_exists('user') and column_exists('unit', 'created_by'):
        safe_create_foreign_key('fk_unit_created_by_user', 'unit', 'user', ['created_by'], ['id'])
    
    if table_exists('unit') and table_exists('organization') and column_exists('unit', 'organization_id'):
        safe_create_foreign_key('fk_unit_organization', 'unit', 'organization', ['organization_id'], ['id'])
    
    print("✅ All missing production columns migration completed")

def downgrade():
    """Remove the added columns and constraints"""
    print("=== Removing Added Production Columns ===")
    
    # Drop foreign key constraints first using batch mode for SQLite
    constraint_drops = [
        ('role', 'fk_role_organization'),
        ('role', 'fk_role_created_by_user'), 
        ('unit', 'fk_unit_organization'),
        ('unit', 'fk_unit_created_by_user')
    ]
    
    for table_name, constraint_name in constraint_drops:
        if table_exists(table_name) and foreign_key_exists(table_name, constraint_name):
            try:
                with op.batch_alter_table(table_name, schema=None) as batch_op:
                    batch_op.drop_constraint(constraint_name, type_='foreignkey')
                print(f"   ✅ Dropped foreign key {constraint_name}")
            except Exception as e:
                print(f"   ⚠️  Could not drop foreign key {constraint_name}: {e}")
    
    # Drop columns in reverse order
    columns_to_drop = [
        ('unit', 'updated_at'),
        ('unit', 'created_at'),
        ('unit', 'is_active'),
        ('role', 'is_system_role'),
        ('role', 'organization_id'),
        ('role', 'created_by'),
        ('role', 'created_at'),
        ('role', 'is_active'),
        ('ingredient_category', 'description'),
        ('developer_permission', 'is_active'),
        ('developer_permission', 'category'),
    ]
    
    for table_name, column_name in columns_to_drop:
        if table_exists(table_name) and column_exists(table_name, column_name):
            try:
                op.drop_column(table_name, column_name)
                print(f"   ✅ Dropped {column_name} from {table_name}")
            except Exception as e:
                print(f"   ⚠️  Could not drop {column_name} from {table_name}: {e}")
    
    print("✅ Production columns downgrade completed")
