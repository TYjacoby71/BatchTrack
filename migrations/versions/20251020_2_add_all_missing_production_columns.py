
"""Add all missing production columns that exist in models but not in database

Revision ID: 20251020_2
Revises: 20251020_1
Create Date: 2025-10-20 00:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect
from migrations.migration_helpers import (
    with_sqlite_cleanup,
    table_exists,
    column_exists,
    foreign_key_exists,
    safe_add_column,
    safe_create_foreign_key,
)

# revision identifiers, used by Alembic.
revision = '20251020_2'
down_revision = '20251020_1'
branch_labels = None
depends_on = None

"""
This migration uses standardized helpers and performs a SQLite temp-table
cleanup prior to applying schema changes. The cleanup is a no-op on
PostgreSQL but ensures reliable reruns on SQLite after partial failures.
"""

def upgrade():
    """Add all missing columns that exist in models but not in database schema"""
    print("=== Adding All Missing Production Columns ===")
    with with_sqlite_cleanup():
        # Fix developer_permission.category - missing column
        if table_exists('developer_permission'):
            safe_add_column('developer_permission', 'category', 
                           sa.Column('category', sa.String(length=64), nullable=True))

        # Fix unit.is_active - missing column
        if table_exists('unit'):
            safe_add_column('unit', 'is_active', 
                           sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))

        # Fix role.is_active - missing column  
        if table_exists('role'):
            safe_add_column('role', 'is_active', 
                           sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))

        # Fix ingredient_category.description - missing column
        if table_exists('ingredient_category'):
            safe_add_column('ingredient_category', 'description', 
                           sa.Column('description', sa.Text(), nullable=True))

        # Add any other missing columns that might be needed for production

        # Fix developer_permission missing columns if they exist in model
        if table_exists('developer_permission'):
            safe_add_column('developer_permission', 'is_active', 
                           sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))

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
                           sa.Column('is_system_role', sa.Boolean(), nullable=False, server_default='false'))

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
    
    # Drop foreign key constraints first
    try:
        if foreign_key_exists('role', 'fk_role_organization'):
            op.drop_constraint('fk_role_organization', 'role', type_='foreignkey')
    except Exception:
        pass
    
    try:
        if foreign_key_exists('role', 'fk_role_created_by_user'):
            op.drop_constraint('fk_role_created_by_user', 'role', type_='foreignkey')
    except Exception:
        pass
    
    try:
        if foreign_key_exists('unit', 'fk_unit_organization'):
            op.drop_constraint('fk_unit_organization', 'unit', type_='foreignkey')
    except Exception:
        pass
    
    try:
        if foreign_key_exists('unit', 'fk_unit_created_by_user'):
            op.drop_constraint('fk_unit_created_by_user', 'unit', type_='foreignkey')
    except Exception:
        pass
    
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
