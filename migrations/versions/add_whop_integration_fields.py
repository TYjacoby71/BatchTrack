"""Add Whop integration fields to Organization

Revision ID: whop_integration
Revises: add_billing_columns_org
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'whop_integration'
down_revision = 'add_billing_columns_org'
branch_labels = None
depends_on = None

def upgrade():
    """Add Whop integration fields to Organization"""
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

    print("=== Adding Whop integration fields ===")

    # Add Whop integration columns only if they don't exist
    whop_columns = [
        ('whop_license_key', sa.String(128)),
        ('whop_product_tier', sa.String(32)),
        ('whop_verified', sa.Boolean())
    ]

    for col_name, col_type in whop_columns:
        if not column_exists('organization', col_name):
            print(f"   Adding {col_name} column...")
            if col_name == 'whop_verified':
                op.add_column('organization', sa.Column(col_name, col_type, default=False, server_default='false'))
            else:
                op.add_column('organization', sa.Column(col_name, col_type, nullable=True))
            print(f"   ✅ Added {col_name}")
        else:
            print(f"   ⚠️  {col_name} column already exists, skipping")

    print("✅ Whop integration fields migration completed")


def downgrade():
    """Remove Whop integration fields from Organization"""
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

    print("=== Removing Whop integration fields ===")

    whop_columns = ['whop_verified', 'whop_product_tier', 'whop_license_key']

    for col_name in whop_columns:
        if column_exists('organization', col_name):
            print(f"   Removing {col_name} column...")
            op.drop_column('organization', col_name)
            print(f"   ✅ Removed {col_name}")
        else:
            print(f"   ⚠️  {col_name} column does not exist, skipping")

    print("✅ Whop integration fields downgrade completed")