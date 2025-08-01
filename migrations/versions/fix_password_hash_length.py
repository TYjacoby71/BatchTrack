
"""fix password_hash column length

Revision ID: fix_password_hash_length
Revises: add_missing_table_schemas
Create Date: 2025-02-01 02:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'fix_password_hash_length'
down_revision = 'add_missing_table_schemas'
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
    """Increase password_hash column length to accommodate modern hashes"""
    print("=== Fixing password_hash column length ===")
    
    if table_exists('user') and column_exists('user', 'password_hash'):
        print("   Updating user.password_hash column length from 120 to 255...")
        
        # Use batch operations for SQLite compatibility
        with op.batch_alter_table('user', schema=None) as batch_op:
            batch_op.alter_column('password_hash',
                                existing_type=sa.String(length=120),
                                type_=sa.String(length=255),
                                existing_nullable=False)
        
        print("   ✅ Updated password_hash column to varchar(255)")
    else:
        print("   ⚠️  User table or password_hash column not found")
    
    print("✅ Migration completed: password_hash column can now store longer hashes")


def downgrade():
    """Revert password_hash column length back to 120"""
    print("=== Reverting password_hash column length ===")
    
    if table_exists('user') and column_exists('user', 'password_hash'):
        print("   Reverting user.password_hash column length from 255 to 120...")
        
        with op.batch_alter_table('user', schema=None) as batch_op:
            batch_op.alter_column('password_hash',
                                existing_type=sa.String(length=255),
                                type_=sa.String(length=120),
                                existing_nullable=False)
        
        print("   ✅ Reverted password_hash column to varchar(120)")
    
    print("✅ Downgrade completed")
