
"""fix missing oauth columns postgresql

Revision ID: 9a2b8c4d5e6f
Revises: add_fallback_price_column
Create Date: 2025-08-06 23:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a2b8c4d5e6f'
down_revision = 'add_fallback_price_column'
branch_labels = None
depends_on = None


def upgrade():
    """Add missing OAuth columns with proper database compatibility"""
    from sqlalchemy import inspect

    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)

    def column_exists(table_name, column_name):
        """Check if a column exists in a table (works for both SQLite and PostgreSQL)"""
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception as e:
            print(f"Error checking column {column_name}: {e}")
            return False

    print("=== OAuth Column Fix (SQLite/PostgreSQL compatible) ===")

    # Add missing OAuth and related columns to user table
    oauth_columns = [
        ('oauth_provider', sa.String(length=50)),
        ('oauth_provider_id', sa.String(length=255)),
        ('password_reset_token', sa.String(length=255)),
        ('password_reset_sent_at', sa.DateTime()),
        ('email_verification_sent_at', sa.DateTime())
    ]

    columns_to_add = []
    for col_name, col_type in oauth_columns:
        if not column_exists('user', col_name):
            columns_to_add.append((col_name, col_type))
            print(f"   Will add {col_name} column...")
        else:
            print(f"   ⚠️  {col_name} column already exists, skipping")

    # Only perform batch operation if there are columns to add
    if columns_to_add:
        with op.batch_alter_table('user', schema=None) as batch_op:
            for col_name, col_type in columns_to_add:
                print(f"   Adding {col_name} column...")
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True))
    else:
        print("   No columns to add - all OAuth columns already exist")

    print("✅ OAuth columns migration completed")


def downgrade():
    """Remove OAuth columns"""
    from sqlalchemy import inspect

    # Get database connection and inspector
    connection = op.get_bind()
    inspector = inspect(connection)

    def column_exists(table_name, column_name):
        """Check if a column exists in a table"""
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception:
            return False

    print("=== OAuth Column Removal ===")

    oauth_columns = [
        'password_reset_sent_at',
        'password_reset_token', 
        'oauth_provider_id',
        'oauth_provider',
        'email_verification_sent_at'
    ]

    with op.batch_alter_table('user', schema=None) as batch_op:
        for col_name in oauth_columns:
            if column_exists('user', col_name):
                print(f"   Dropping {col_name} column...")
                batch_op.drop_column(col_name)
            else:
                print(f"   ⚠️  {col_name} column doesn't exist, skipping")

    print("✅ OAuth columns removal completed")
