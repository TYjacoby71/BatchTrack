
"""add missing permission category column

Revision ID: add_missing_permission_category_column
Revises: add_missing_user_columns
Create Date: 2025-08-25 17:36:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_perm_category_col'
down_revision = 'add_missing_user_columns'
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    """Check if a column exists in the database"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def upgrade():
    """Add missing category column to permission table"""
    print("=== Adding missing permission.category column ===")
    
    if not column_exists('permission', 'category'):
        print("   Adding category column...")
        op.add_column('permission', sa.Column('category', sa.String(64), nullable=True))
        print("   ✅ category column added successfully")
    else:
        print("   ✅ category column already exists")
    
    print("✅ Permission category column migration completed")

def downgrade():
    """Remove the category column"""
    if column_exists('permission', 'category'):
        op.drop_column('permission', 'category')
